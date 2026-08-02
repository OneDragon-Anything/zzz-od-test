from pathlib import Path
from types import SimpleNamespace

import pytest

import one_dragon.envs.git_service as git_service_module
from one_dragon.envs.git_service import GitService, GitSyncStatus


def test_status_values_are_neutral_user_messages() -> None:
    assert {status: status.value for status in GitSyncStatus} == {
        GitSyncStatus.SUCCESS: '更新完成',
        GitSyncStatus.UP_TO_DATE: '当前已是最新版本',
        GitSyncStatus.RUNTIME_INCOMPATIBLE: '新版本需要更新启动器才能使用',
        GitSyncStatus.BUILTIN_TAG_UNAVAILABLE: '暂时无法获取当前版本所需文件',
        GitSyncStatus.REMOTE_UNAVAILABLE: '暂时无法获取更新',
        GitSyncStatus.LOCAL_CHANGES: '检测到程序文件有改动，未自动更新',
        GitSyncStatus.LOCAL_UPDATE_FAILED: '更新没有完成',
        GitSyncStatus.FAILED: '更新失败',
    }


def create_git_service(tmp_path: Path) -> GitService:
    env_config = SimpleNamespace(
        git_remote='origin',
        git_branch='main',
        force_update=False,
    )
    return GitService(
        SimpleNamespace(),
        env_config,
        SimpleNamespace(),
        repo_dir=str(tmp_path),
    )


@pytest.mark.parametrize(
    ('branch_changed', 'expected_status', 'expected_message'),
    [
        (False, GitSyncStatus.UP_TO_DATE, '当前已是最新版本'),
        (True, GitSyncStatus.SUCCESS, '更新完成'),
    ],
)
def test_fetch_and_checkout_distinguishes_up_to_date_from_branch_switch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    branch_changed: bool,
    expected_status: GitSyncStatus,
    expected_message: str,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(
        git_service,
        '_fetch_remote',
        lambda progress_callback, stage_start, stage_end: (GitSyncStatus.SUCCESS, ''),
    )
    monkeypatch.setattr(git_service, '_check_remote_manifest_compatible', lambda: (True, ''))
    monkeypatch.setattr(
        git_service,
        '_validate_working_directory',
        lambda: (GitSyncStatus.SUCCESS, ''),
    )
    monkeypatch.setattr(
        git_service,
        '_checkout_branch',
        lambda: (GitSyncStatus.SUCCESS, branch_changed, ''),
    )
    monkeypatch.setattr(
        git_service,
        '_sync_with_remote',
        lambda force: (GitSyncStatus.UP_TO_DATE, '当前已是最新版本'),
    )

    status, message = git_service._fetch_and_checkout_latest_branch()

    assert status is expected_status
    assert message == expected_message


def test_builtin_tag_does_not_hide_local_update_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(git_service_module, 'init_repository', lambda path: None)
    monkeypatch.setattr(
        git_service,
        '_fetch_remote',
        lambda progress_callback, stage_start, stage_end, tag_name: (
            GitSyncStatus.LOCAL_UPDATE_FAILED,
            '本地代码更新失败',
        ),
    )

    status, message = git_service._clone_repository(initial_tag='v1.0.0')

    assert status is GitSyncStatus.LOCAL_UPDATE_FAILED
    assert message == '本地代码更新失败'


def test_validate_working_directory_returns_local_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(git_service, '_open_repo', lambda: SimpleNamespace(status=lambda: {'file.py': 1}))

    status, message = git_service._validate_working_directory()

    assert status is GitSyncStatus.LOCAL_CHANGES
    assert message == '检测到程序文件有改动'


def test_validate_working_directory_failure_is_local_update_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(
        git_service,
        '_open_repo',
        lambda: (_ for _ in ()).throw(RuntimeError('仓库不可读')),
    )

    status, message = git_service._validate_working_directory()

    assert status is GitSyncStatus.LOCAL_UPDATE_FAILED
    assert message == '检测当前代码状态失败'


def test_sync_with_remote_returns_up_to_date_when_commit_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(git_service, '_get_local_and_remote_oid', lambda: ('same', 'same', ''))

    status, message = git_service._sync_with_remote(force=False)

    assert status is GitSyncStatus.UP_TO_DATE
    assert message == '当前已是最新版本'


def test_sync_with_remote_returns_local_changes_when_update_cannot_fast_forward(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(git_service, '_get_local_and_remote_oid', lambda: ('local', 'remote', ''))
    monkeypatch.setattr(
        git_service,
        '_open_repo',
        lambda: SimpleNamespace(
            descendant_of=lambda remote, local: False,
            status=lambda: {},
        ),
    )

    status, message = git_service._sync_with_remote(force=False)

    assert status is GitSyncStatus.LOCAL_CHANGES
    assert message == '检测到程序文件有改动'


def test_checkout_failure_is_local_update_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    repo = SimpleNamespace(
        head=SimpleNamespace(name='refs/heads/main'),
        references={},
    )
    monkeypatch.setattr(git_service, '_open_repo', lambda: repo)

    status, branch_changed, message = git_service._checkout_branch()

    assert status is GitSyncStatus.LOCAL_UPDATE_FAILED
    assert branch_changed is False
    assert message == '切换到目标版本失败'


def test_fetch_latest_code_returns_neutral_message_for_known_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(git_service, 'is_initial_checkout_pending', lambda: False)
    monkeypatch.setattr(
        git_service,
        '_fetch_and_checkout_latest_branch',
        lambda progress_callback: (
            GitSyncStatus.RUNTIME_INCOMPATIBLE,
            '目标版本的运行环境与当前不兼容',
        ),
    )

    status, message = git_service.fetch_latest_code()

    assert status is GitSyncStatus.RUNTIME_INCOMPATIBLE
    assert message == '新版本需要更新启动器才能使用'


def test_fetch_latest_code_uses_failed_only_for_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_service = create_git_service(tmp_path)
    monkeypatch.setattr(git_service, 'is_initial_checkout_pending', lambda: False)
    monkeypatch.setattr(
        git_service,
        '_fetch_and_checkout_latest_branch',
        lambda progress_callback: (_ for _ in ()).throw(RuntimeError('意外错误')),
    )

    status, message = git_service.fetch_latest_code()

    assert status is GitSyncStatus.FAILED
    assert message == '更新失败'
