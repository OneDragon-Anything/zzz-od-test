"""验证 Git 服务读取目标清单，并在切换代码前调用运行时兼容性检查。"""

import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pygit2 import Oid

from one_dragon.envs.git_service import GitService, GitSyncStatus

ManifestCheck = Callable[[bytes, bytes], tuple[bool, str]]
TARGET_OID = Oid(hex='1' * 40)


@pytest.fixture
def check_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ManifestCheck:
    """提供不连接远程仓库、使用真实兼容性检查模块的冻结环境检查。"""
    service = GitService.__new__(GitService)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    monkeypatch.setattr(
        service,
        '_get_manifest_path_from_commit',
        lambda _oid: 'deploy/module_manifest.py',
    )

    def check(local: bytes, remote: bytes) -> tuple[bool, str]:
        """写入本地基准并检查给定目标清单。"""
        (tmp_path / 'module_manifest.py').write_bytes(local)
        monkeypatch.setattr(
            service,
            '_get_file_at_commit',
            lambda _oid, _path: remote,
        )
        return service._check_manifest_compatible(TARGET_OID)

    return check


@pytest.mark.parametrize('manifest_path', ['deploy/module_manifest.py', 'deploy/renamed_manifest.py'])
@pytest.mark.parametrize('compatible', [True, False])
def test_target_commit_manifests_are_passed_to_runtime_checker(
    monkeypatch: pytest.MonkeyPatch,
    manifest_path: str,
    compatible: bool,
) -> None:
    """Git 服务只负责按目标提交配置读清单、调用检查并转换结果。"""
    service = GitService.__new__(GitService)
    local = b'import sys\n'
    remote = b'import sys\nimport json\n'
    read_file = Mock(side_effect=[f'manifest_path: {manifest_path}\n'.encode(), remote])
    checker = Mock(return_value=compatible)
    monkeypatch.setattr('one_dragon.envs.git_service.load_runtime_manifest', Mock(return_value=local))
    monkeypatch.setattr('one_dragon.envs.git_service.check_manifest_compatible', checker)
    monkeypatch.setattr(service, '_get_file_at_commit', read_file)

    result, message = service._check_manifest_compatible(TARGET_OID)

    assert result is compatible
    assert bool(message) is not compatible
    assert [call.args for call in read_file.call_args_list] == [
        (TARGET_OID, 'config/project.yml'),
        (TARGET_OID, manifest_path),
    ]
    checker.assert_called_once_with(local, remote)


def test_unavailable_runtime_manifest_skips_target_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """运行时检查模块未提供打包清单时，不读取目标版本。"""
    service = GitService.__new__(GitService)
    lookup = Mock(side_effect=AssertionError('缺少本地基准时不应读取目标清单'))
    checker = Mock(side_effect=AssertionError('缺少本地基准时不应检查'))
    monkeypatch.setattr('one_dragon.envs.git_service.load_runtime_manifest', Mock(return_value=None))
    monkeypatch.setattr('one_dragon.envs.git_service.check_manifest_compatible', checker)
    monkeypatch.setattr(service, '_get_manifest_path_from_commit', lookup)

    assert service._check_manifest_compatible(TARGET_OID) == (True, '')
    lookup.assert_not_called()
    checker.assert_not_called()


@pytest.mark.parametrize(
    'project_config',
    [None, b'{}\n', b'manifest_path: deploy/module_manifest.py\n'],
)
def test_missing_target_config_or_manifest_blocks_update(
    monkeypatch: pytest.MonkeyPatch,
    project_config: bytes | None,
) -> None:
    """本地清单可用时，目标配置、清单路径或清单文件缺失都阻止更新。"""
    service = GitService.__new__(GitService)
    read_file = Mock(side_effect=[project_config, None])
    checker = Mock(side_effect=AssertionError('缺少目标清单时不应检查'))
    monkeypatch.setattr('one_dragon.envs.git_service.load_runtime_manifest', Mock(return_value=b'import sys\n'))
    monkeypatch.setattr('one_dragon.envs.git_service.check_manifest_compatible', checker)
    monkeypatch.setattr(service, '_get_file_at_commit', read_file)

    compatible, message = service._check_manifest_compatible(TARGET_OID)
    assert compatible is False
    assert message
    checker.assert_not_called()


def test_manifest_check_exception_blocks_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """本地清单可用且清单检查抛异常时阻止更新。"""
    service = GitService.__new__(GitService)
    monkeypatch.setattr('one_dragon.envs.git_service.load_runtime_manifest', Mock(return_value=b'import sys\n'))
    monkeypatch.setattr(
        'one_dragon.envs.git_service.check_manifest_compatible',
        Mock(side_effect=RuntimeError('检查失败')),
    )
    monkeypatch.setattr(
        service,
        '_get_file_at_commit',
        lambda _oid, path: b'manifest_path: deploy/module_manifest.py\n' if path.endswith('project.yml') else b'import sys\n',
    )

    compatible, message = service._check_manifest_compatible(TARGET_OID)
    assert compatible is False
    assert message


@pytest.mark.parametrize('local_manifest', [b'import sys\n', None])
def test_remote_manifest_exception_uses_local_manifest_availability(
    monkeypatch: pytest.MonkeyPatch,
    local_manifest: bytes | None,
) -> None:
    """远程检查异常仅在本地冻结清单不可用时跳过。"""
    service = GitService.__new__(GitService)
    service.env_config = SimpleNamespace(git_remote='origin', git_branch='main')
    monkeypatch.setattr('one_dragon.envs.git_service.load_runtime_manifest', Mock(return_value=local_manifest))
    monkeypatch.setattr(service, '_open_repo', Mock(side_effect=RuntimeError('仓库不可用')))

    compatible, message = service._check_remote_manifest_compatible()
    assert compatible is (local_manifest is None)
    assert bool(message) is (local_manifest is not None)


@pytest.mark.parametrize('operation', ['update', 'clone', 'reset'])
@pytest.mark.parametrize(
    ('remote', 'compatible'),
    [
        (b'import sys\nimport json\n', True),
        (b'from math import nonexistent_symbol_20261025\n', False),
        (b'import nonexistent_runtime_dependency_20261025\n', False),
    ],
)
def test_code_changes_require_compatible_imports_before_checkout_or_reset(
    check_manifest: ManifestCheck,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    operation: str,
    remote: bytes,
    compatible: bool,
) -> None:
    """更新、首次同步和回滚均在切换代码前按真实清单检查结果放行或拦截。"""
    service = GitService.__new__(GitService)
    service.repo_dir = str(tmp_path / 'repository')
    service.env_config = SimpleNamespace(git_remote='origin', git_branch='main', force_update=False)
    repo = SimpleNamespace(
        references={'refs/remotes/origin/main': SimpleNamespace(target=TARGET_OID)},
        revparse_single=Mock(return_value=SimpleNamespace(id=TARGET_OID)),
    )
    check = Mock(side_effect=lambda _oid: check_manifest(b'import sys\n', remote))
    fetch = Mock(return_value=(GitSyncStatus.SUCCESS, ''))
    validate = Mock(return_value=(GitSyncStatus.SUCCESS, ''))
    checkout = Mock(return_value=(GitSyncStatus.SUCCESS, False, ''))
    sync = Mock(return_value=(GitSyncStatus.SUCCESS, ''))
    reset = Mock(return_value=True)
    monkeypatch.setattr(service, '_open_repo', Mock(return_value=repo))
    monkeypatch.setattr(service, '_check_manifest_compatible', check)
    monkeypatch.setattr(service, '_fetch_remote', fetch)
    monkeypatch.setattr(service, '_validate_working_directory', validate)
    monkeypatch.setattr(service, '_checkout_branch', checkout)
    monkeypatch.setattr(service, '_sync_with_remote', sync)
    monkeypatch.setattr(service, '_reset_hard', reset)
    monkeypatch.setattr('one_dragon.envs.git_service.init_repository', Mock())

    if operation == 'reset':
        succeeded, _ = service.reset_to_commit(str(TARGET_OID))
        assert succeeded is compatible
        if compatible:
            reset.assert_called_once_with(TARGET_OID)
        else:
            reset.assert_not_called()
        checkout.assert_not_called()
        sync.assert_not_called()
        fetch.assert_not_called()
    else:
        if operation == 'clone':
            status, _ = service._clone_repository()
        else:
            status, _ = service._fetch_and_checkout_latest_branch()
        expected_status = GitSyncStatus.SUCCESS if compatible else GitSyncStatus.RUNTIME_INCOMPATIBLE
        assert status is expected_status
        fetch.assert_called_once()
        if compatible:
            checkout.assert_called_once_with()
            sync.assert_called_once()
        else:
            validate.assert_not_called()
            checkout.assert_not_called()
            sync.assert_not_called()
        reset.assert_not_called()

    check.assert_called_once_with(TARGET_OID)


def test_initial_builtin_tag_keeps_skipping_manifest_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """首次按内置 tag 同步仍不额外检查与其配套的清单。"""
    service = GitService.__new__(GitService)
    service.repo_dir = str(tmp_path / 'repository')
    fetch = Mock(return_value=(GitSyncStatus.SUCCESS, ''))
    check = Mock(side_effect=AssertionError('内置 tag 不应检查清单'))
    monkeypatch.setattr('one_dragon.envs.git_service.init_repository', Mock())
    monkeypatch.setattr(service, '_fetch_remote', fetch)
    monkeypatch.setattr(service, '_check_remote_manifest_compatible', check)
    monkeypatch.setattr(service, '_checkout_branch', Mock(return_value=(GitSyncStatus.SUCCESS, False, '')))
    monkeypatch.setattr(service, '_sync_with_remote', Mock(return_value=(GitSyncStatus.SUCCESS, '')))

    status, _ = service._clone_repository(initial_tag='v1.2.3')

    assert status is GitSyncStatus.SUCCESS
    fetch.assert_called_once_with(None, 2 / 6, 3 / 6, 'v1.2.3')
    check.assert_not_called()


def test_non_frozen_environment_skips_manifest_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """源码运行仍不受集成运行时清单限制。"""
    service = GitService.__new__(GitService)
    lookup = Mock(side_effect=AssertionError('源码模式不应读取清单'))
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    monkeypatch.setattr(service, '_get_manifest_path_from_commit', lookup)

    assert service._check_manifest_compatible(TARGET_OID) == (True, '')
    lookup.assert_not_called()
