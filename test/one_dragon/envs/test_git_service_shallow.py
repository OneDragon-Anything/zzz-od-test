"""测试 GitService 的仓库级 shallow 状态迁移。"""

import contextlib
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pygit2
import pytest

import one_dragon.envs.git_service as git_service_module
from one_dragon.envs.git_service import (
    GitService,
    GitSyncStatus,
    _fetch_remote_worker,
    _get_repository_objects_path,
    _LocalGitMetadataError,
    _parse_shallow_snapshot,
    _read_shallow_snapshot,
    _sync_shallow_file,
)


def _create_commit(
    repo: pygit2.Repository,
    ref_name: str,
    message: str,
    parents: list[pygit2.Oid],
) -> pygit2.Oid:
    tree_builder = repo.TreeBuilder()
    blob_id = repo.create_blob(message.encode('utf-8'))
    tree_builder.insert('README.md', blob_id, pygit2.GIT_FILEMODE_BLOB)
    tree_id = tree_builder.write()
    signature = pygit2.Signature('test', 'test@example.com')
    return repo.create_commit(
        ref_name,
        signature,
        signature,
        message,
        tree_id,
        parents,
    )


def _create_service(
    repo_path: Path,
    branch_name: str,
    primary_branch: str = 'main',
) -> GitService:
    env_config = SimpleNamespace(
        git_branch=branch_name,
        git_remote='origin',
        is_personal_proxy=False,
        personal_proxy='',
    )
    return GitService(
        env_config,
        SimpleNamespace(primary_branch=primary_branch),
        repo_dir=str(repo_path),
    )


def _capture_fetch_request(
    git_service: GitService,
    monkeypatch: pytest.MonkeyPatch,
    temp_root: Path,
) -> tuple[object, ...]:
    captured: list[tuple[object, ...]] = []

    def fake_worker(*args: object) -> None:
        captured.append(args)
        message_callback = args[6]
        assert callable(message_callback)
        message_callback(
            {
                'type': 'result',
                'success': True,
                'primary_branch_incremental': bool(args[11]),
                'shallow_authoritative': True,
            }
        )

    monkeypatch.setattr(git_service_module, '_fetch_remote_worker', fake_worker)
    monkeypatch.setattr(
        git_service_module.os_utils,
        'get_path_under_work_dir',
        lambda *sub_paths: str(temp_root.joinpath(*sub_paths)),
    )
    monkeypatch.setattr(git_service, '_import_fetch_result', lambda *args: None)

    git_service._fetch_remote_once('https://example.com/repo.git', None, 0.0, 1.0)

    assert len(captured) == 1
    return captured[0]


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ['git', *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    return result.stdout.strip()


@contextlib.contextmanager
def _serve_git_daemon(repository_root: Path) -> Iterator[str]:
    if shutil.which('git') is None:
        pytest.skip('当前环境没有 git 命令')

    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = int(probe.getsockname()[1])

    process = subprocess.Popen(
        [
            'git',
            'daemon',
            '--reuseaddr',
            '--export-all',
            f'--base-path={repository_root}',
            '--listen=127.0.0.1',
            f'--port={port}',
            str(repository_root),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
    )
    try:
        remote_url = f'git://127.0.0.1:{port}/repo.git'
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr is not None else ''
                pytest.skip(f'当前环境无法启动 git daemon: {stderr.strip()}')
            readiness = subprocess.run(
                ['git', 'ls-remote', remote_url],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=1,
            )
            if readiness.returncode == 0:
                break
            time.sleep(0.05)
        else:
            pytest.skip('git daemon 未在预期时间内启动')
        yield remote_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def test_sync_shallow_file_writes_authoritative_repository_state(tmp_path: Path) -> None:
    first_oid = '1' * 40
    second_oid = '2' * 40
    target_path = tmp_path / 'target'
    temp_repo_dir = tmp_path / 'temp'
    temp_repo_dir.mkdir()
    repo = pygit2.init_repository(str(target_path))
    target_shallow = Path(repo.path) / 'shallow'
    target_shallow.write_bytes(f'{first_oid}\n'.encode('ascii'))
    fetched_snapshot = f'{first_oid}\n{second_oid}\n'.encode('ascii')
    (temp_repo_dir / 'shallow').write_bytes(fetched_snapshot)

    _sync_shallow_file(
        repo,
        str(temp_repo_dir),
        target_shallow.read_bytes(),
        True,
    )

    assert target_shallow.read_bytes() == fetched_snapshot
    assert b'\r' not in target_shallow.read_bytes()


def test_sync_shallow_file_removes_file_for_authoritative_empty_state(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / 'target'
    temp_repo_dir = tmp_path / 'temp'
    temp_repo_dir.mkdir()
    repo = pygit2.init_repository(str(target_path))
    target_shallow = Path(repo.path) / 'shallow'
    original_snapshot = f"{'1' * 40}\n".encode('ascii')
    target_shallow.write_bytes(original_snapshot)

    _sync_shallow_file(repo, str(temp_repo_dir), original_snapshot, True)

    assert not target_shallow.exists()


def test_sync_shallow_file_conservatively_adds_boundaries(tmp_path: Path) -> None:
    first_oid = '1' * 40
    second_oid = '2' * 40
    target_path = tmp_path / 'target'
    temp_repo_dir = tmp_path / 'temp'
    temp_repo_dir.mkdir()
    repo = pygit2.init_repository(str(target_path))
    target_shallow = Path(repo.path) / 'shallow'
    original_snapshot = f'{first_oid}\n'.encode('ascii')
    target_shallow.write_bytes(original_snapshot)
    (temp_repo_dir / 'shallow').write_bytes(f'{second_oid}\n'.encode('ascii'))

    _sync_shallow_file(repo, str(temp_repo_dir), original_snapshot, False)

    assert _parse_shallow_snapshot(target_shallow.read_bytes()) == [
        first_oid,
        second_oid,
    ]


def test_fetch_remote_rebuilds_malformed_shallow_without_source_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    shallow_path = Path(repo.path) / 'shallow'
    shallow_bytes = b'invalid\r\n'
    shallow_path.write_bytes(shallow_bytes)
    repo.free()
    git_service = _create_service(repo_path, 'main')
    candidates = [
        (SimpleNamespace(config_item=SimpleNamespace(ui_text='first'), url='first'), 'first'),
        (SimpleNamespace(config_item=SimpleNamespace(ui_text='second'), url='second'), 'second'),
    ]
    attempted_urls: list[str] = []
    rebuild_calls: list[tuple[object, str | None]] = []
    restore_calls: list[bool] = []
    original_fetch_once = git_service._fetch_remote_once

    monkeypatch.setattr(git_service, '_get_repository_candidates', lambda: candidates)
    monkeypatch.setattr(
        git_service,
        '_get_repository_item',
        lambda repository: repository.config_item,
    )

    def fetch_once(*args: object) -> None:
        attempted_urls.append(str(args[0]))
        original_fetch_once(*args)

    monkeypatch.setattr(git_service, '_fetch_remote_once', fetch_once)
    monkeypatch.setattr(
        git_service,
        '_rebuild_repository',
        lambda progress_callback, initial_tag: (
            rebuild_calls.append((progress_callback, initial_tag))
            or (GitSyncStatus.SUCCESS, '更新完成')
        ),
    )
    monkeypatch.setattr(git_service, '_restore_origin', lambda: restore_calls.append(True) or True)

    status, message = git_service._fetch_remote(tag_name='v1.0.0')

    assert status is GitSyncStatus.SUCCESS
    assert message == '更新完成'
    assert attempted_urls == ['first']
    assert rebuild_calls == [(None, 'v1.0.0')]
    assert restore_calls == []
    assert shallow_path.read_bytes() == shallow_bytes


def test_existing_target_with_undeclared_gap_triggers_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    root_oid = _create_commit(repo, 'refs/heads/feature', 'root', [])
    tip_oid = _create_commit(repo, 'refs/heads/feature', 'tip', [root_oid])
    root_object = _get_repository_objects_path(repo) / str(root_oid)[:2] / str(root_oid)[2:]
    repo.free()
    root_object.chmod(0o666)
    root_object.unlink()
    git_service = _create_service(repo_path, 'feature')
    candidate = (
        SimpleNamespace(config_item=SimpleNamespace(ui_text='first'), url='first'),
        'first',
    )
    rebuild_calls: list[tuple[object, str | None]] = []

    monkeypatch.setattr(git_service, '_get_repository_candidates', lambda: [candidate])
    monkeypatch.setattr(
        git_service,
        '_get_repository_item',
        lambda repository: repository.config_item,
    )
    monkeypatch.setattr(
        git_service,
        '_rebuild_repository',
        lambda progress_callback, initial_tag: (
            rebuild_calls.append((progress_callback, initial_tag))
            or (GitSyncStatus.SUCCESS, '更新完成')
        ),
    )

    status, _ = git_service._fetch_remote()

    assert status is GitSyncStatus.SUCCESS
    assert rebuild_calls == [(None, None)]
    with pytest.raises(_LocalGitMetadataError):
        git_service._validate_history(git_service._open_repo(), tip_oid)


def test_existing_legal_shallow_target_uses_own_incremental_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    root_oid = _create_commit(repo, 'refs/heads/feature', 'root', [])
    tip_oid = _create_commit(repo, 'refs/heads/feature', 'tip', [root_oid])
    shallow_snapshot = f'{root_oid}\n'.encode('ascii')
    (Path(repo.path) / 'shallow').write_bytes(shallow_snapshot)
    repo.free()
    git_service = _create_service(repo_path, 'feature')

    worker_args = _capture_fetch_request(git_service, monkeypatch, tmp_path / 'worker')

    assert worker_args[4] == 0
    assert worker_args[9] == 'refs/heads/feature'
    assert worker_args[10] == str(tip_oid)
    assert worker_args[11] is False
    assert worker_args[12] == shallow_snapshot


def test_first_non_primary_branch_uses_configured_complete_primary_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    primary_oid = _create_commit(
        repo,
        'refs/remotes/origin/develop',
        'develop',
        [],
    )
    repo.free()
    git_service = _create_service(repo_path, 'feature', primary_branch='develop')

    worker_args = _capture_fetch_request(git_service, monkeypatch, tmp_path / 'worker')

    assert worker_args[4] == 0
    assert worker_args[9] == 'refs/heads/develop'
    assert worker_args[10] == str(primary_oid)
    assert worker_args[11] is True


def test_legal_shallow_primary_branch_is_used_for_another_branch_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    primary_oid = _create_commit(
        repo,
        'refs/remotes/origin/develop',
        'develop',
        [],
    )
    shallow_snapshot = f'{primary_oid}\n'.encode('ascii')
    (Path(repo.path) / 'shallow').write_bytes(shallow_snapshot)
    repo.free()
    git_service = _create_service(repo_path, 'feature', primary_branch='develop')

    worker_args = _capture_fetch_request(git_service, monkeypatch, tmp_path / 'worker')

    assert worker_args[4] == 0
    assert worker_args[9] == 'refs/heads/develop'
    assert worker_args[10] == str(primary_oid)
    assert worker_args[11] is True
    assert worker_args[12] == shallow_snapshot


def test_linear_history_gap_appends_single_shallow_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    root_oid = _create_commit(repo, 'refs/heads/develop', 'root', [])
    reachable_oid = _create_commit(
        repo,
        'refs/heads/develop',
        'reachable',
        [root_oid],
    )
    tip_oid = _create_commit(
        repo,
        'refs/remotes/origin/develop',
        'tip',
        [reachable_oid],
    )
    root_object = (
        _get_repository_objects_path(repo) / str(root_oid)[:2] / str(root_oid)[2:]
    )
    repo.free()
    root_object.chmod(0o666)
    root_object.unlink()
    git_service = _create_service(repo_path, 'feature', primary_branch='develop')
    warnings: list[str] = []
    monkeypatch.setattr(
        git_service_module.log,
        'warning',
        lambda *args, **kwargs: warnings.append(str(args[0])),
    )

    worker_args = _capture_fetch_request(git_service, monkeypatch, tmp_path / 'worker')

    assert worker_args[4] == 0
    assert worker_args[9] == 'refs/heads/develop'
    assert worker_args[10] == str(tip_oid)
    assert worker_args[11] is True
    repaired_snapshot = worker_args[12]
    assert _parse_shallow_snapshot(repaired_snapshot) == [str(reachable_oid)]
    opened_repo = git_service._open_repo()
    assert (
        _read_shallow_snapshot(Path(opened_repo.path) / 'shallow') == repaired_snapshot
    )
    assert any('未声明历史缺口' in message for message in warnings)
    assert any(str(reachable_oid) in message for message in warnings)
    assert any(
        'git fetch --unshallow origin develop' in message for message in warnings
    )


def test_derive_boundary_after_merge_uses_first_parent_child(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    root_oid = _create_commit(repo, 'refs/heads/root', 'root', [])
    side_oid = _create_commit(repo, 'refs/heads/side', 'side', [root_oid])
    first_oid = _create_commit(repo, 'refs/heads/first', 'first', [root_oid])
    merge_oid = _create_commit(
        repo,
        'refs/heads/main',
        'merge',
        [first_oid, side_oid],
    )
    after_oid = _create_commit(repo, 'refs/heads/main', 'after', [merge_oid])
    tip_oid = _create_commit(repo, 'refs/heads/main', 'tip', [after_oid])
    first_object = (
        _get_repository_objects_path(repo) / str(first_oid)[:2] / str(first_oid)[2:]
    )
    repo.free()
    first_object.chmod(0o666)
    first_object.unlink()
    git_service = _create_service(repo_path, 'feature')

    boundary_oid = git_service._derive_single_shallow_boundary(
        git_service._open_repo(),
        tip_oid,
    )

    assert boundary_oid == after_oid


def test_derive_boundary_merge_commit_as_tip_uses_merge_itself(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    root_oid = _create_commit(repo, 'refs/heads/root', 'root', [])
    side_oid = _create_commit(repo, 'refs/heads/side', 'side', [root_oid])
    first_oid = _create_commit(repo, 'refs/heads/first', 'first', [root_oid])
    merge_oid = _create_commit(
        repo,
        'refs/heads/main',
        'merge',
        [first_oid, side_oid],
    )
    first_object = (
        _get_repository_objects_path(repo) / str(first_oid)[:2] / str(first_oid)[2:]
    )
    repo.free()
    first_object.chmod(0o666)
    first_object.unlink()
    git_service = _create_service(repo_path, 'feature')

    boundary_oid = git_service._derive_single_shallow_boundary(
        git_service._open_repo(),
        merge_oid,
    )

    assert boundary_oid == merge_oid


def test_repair_keeps_existing_boundary_without_duplicate(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    root_oid = _create_commit(repo, 'refs/heads/develop', 'root', [])
    reachable_oid = _create_commit(
        repo,
        'refs/heads/develop',
        'reachable',
        [root_oid],
    )
    tip_oid = _create_commit(repo, 'refs/heads/develop', 'tip', [reachable_oid])
    other_oid = _create_commit(repo, 'refs/heads/other', 'other', [root_oid])
    other_object = (
        _get_repository_objects_path(repo) / str(other_oid)[:2] / str(other_oid)[2:]
    )
    shallow_snapshot = f'{reachable_oid}\n{other_oid}\n'.encode('ascii')
    (Path(repo.path) / 'shallow').write_bytes(shallow_snapshot)
    root_object = (
        _get_repository_objects_path(repo) / str(root_oid)[:2] / str(root_oid)[2:]
    )
    repo.free()
    root_object.chmod(0o666)
    root_object.unlink()
    other_object.chmod(0o666)
    other_object.unlink()
    git_service = _create_service(repo_path, 'feature', primary_branch='develop')

    repaired_repo, repaired_snapshot = git_service._repair_primary_branch_shallow(
        git_service._open_repo(),
        tip_oid,
        shallow_snapshot,
        'develop',
    )

    assert repaired_snapshot == shallow_snapshot
    assert (
        _read_shallow_snapshot(Path(repaired_repo.path) / 'shallow')
        == shallow_snapshot
    )


def test_repair_rolls_back_and_does_not_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    root_oid = _create_commit(repo, 'refs/heads/develop', 'root', [])
    _create_commit(repo, 'refs/heads/develop', 'reachable', [root_oid])
    _create_commit(repo, 'refs/remotes/origin/develop', 'tip', [])
    root_object = (
        _get_repository_objects_path(repo) / str(root_oid)[:2] / str(root_oid)[2:]
    )
    repo.free()
    root_object.chmod(0o666)
    root_object.unlink()
    git_service = _create_service(repo_path, 'feature', primary_branch='develop')
    validate_calls = 0

    def failing_validate(repo: object, start_oid: pygit2.Oid) -> None:
        nonlocal validate_calls
        validate_calls += 1
        raise _LocalGitMetadataError('commit history has undeclared gap')

    monkeypatch.setattr(
        git_service_module,
        '_fetch_remote_worker',
        lambda *args: None,
    )
    monkeypatch.setattr(
        git_service_module.os_utils,
        'get_path_under_work_dir',
        lambda *sub_paths: str((tmp_path / 'worker').joinpath(*sub_paths)),
    )
    monkeypatch.setattr(git_service, '_import_fetch_result', lambda *args: None)
    monkeypatch.setattr(git_service, '_validate_history', failing_validate)

    with pytest.raises(_LocalGitMetadataError):
        git_service._fetch_remote_once('https://example.com/repo.git', None, 0.0, 1.0)

    assert validate_calls == 2
    assert not (Path(repo_path) / '.git' / 'shallow').exists()


def test_non_missing_object_error_skips_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    _create_commit(repo, 'refs/remotes/origin/develop', 'develop', [])
    repo.free()
    git_service = _create_service(repo_path, 'feature', primary_branch='develop')
    repair_calls: list[object] = []

    monkeypatch.setattr(
        git_service,
        '_validate_history',
        lambda repo, start_oid: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    monkeypatch.setattr(
        git_service,
        '_repair_primary_branch_shallow',
        lambda *args: repair_calls.append(args),
    )

    with pytest.raises(RuntimeError, match='boom'):
        git_service._fetch_remote_once('https://example.com/repo.git', None, 0.0, 1.0)

    assert repair_calls == []


def test_tag_fetch_uses_depth_one_even_when_local_branch_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / 'repo'
    repo = pygit2.init_repository(str(repo_path))
    _create_commit(repo, 'refs/heads/main', 'main', [])
    repo.free()
    git_service = _create_service(repo_path, 'main')
    captured: list[tuple[object, ...]] = []

    def fake_worker(*args: object) -> None:
        captured.append(args)
        message_callback = args[6]
        assert callable(message_callback)
        message_callback(
            {
                'type': 'result',
                'success': True,
                'shallow_authoritative': True,
            }
        )

    monkeypatch.setattr(git_service_module, '_fetch_remote_worker', fake_worker)
    monkeypatch.setattr(
        git_service_module.os_utils,
        'get_path_under_work_dir',
        lambda *sub_paths: str((tmp_path / 'worker').joinpath(*sub_paths)),
    )
    monkeypatch.setattr(git_service, '_import_fetch_result', lambda *args: None)

    git_service._fetch_remote_once(
        'https://example.com/repo.git',
        None,
        0.0,
        1.0,
        'v1.0.0',
    )

    assert captured[0][4] == 1
    assert captured[0][8] == 'refs/tags/v1.0.0'
    assert captured[0][9] is None
    assert captured[0][11] is False


def test_primary_branch_incremental_fallback_restores_initial_shallow_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shallow_snapshot = f"{'1' * 40}\n".encode('ascii')
    temp_repo_dir = tmp_path / 'temp'
    temp_repo_dir.mkdir()
    fetch_calls: list[tuple[list[str], int]] = []
    restore_calls: list[tuple[bytes | None, set[str]]] = []

    class FakeRemote:
        def fetch(
            self,
            *,
            refspecs: list[str],
            proxy: str | None,
            depth: int,
            callbacks: object,
        ) -> None:
            fetch_calls.append((refspecs, depth))
            if depth == 0:
                raise RuntimeError('primary branch incremental failed')

    fake_remote = FakeRemote()

    class FakeRemotes:
        def create(self, name: str, url: str) -> FakeRemote:
            return fake_remote

        def __getitem__(self, name: str) -> FakeRemote:
            return fake_remote

    class FakeReferences(dict[str, pygit2.Oid]):
        def create(
            self,
            name: str,
            oid: pygit2.Oid,
            force: bool,
        ) -> None:
            self[name] = oid

        def delete(self, name: str) -> None:
            self.pop(name, None)

    fake_repo = SimpleNamespace(
        config={},
        references=FakeReferences(),
        remotes=FakeRemotes(),
        free=lambda: None,
    )
    monkeypatch.setattr(git_service_module, 'init_repository', lambda path, bare: fake_repo)
    monkeypatch.setattr(git_service_module, 'Repository', lambda path: fake_repo)
    monkeypatch.setattr(git_service_module, '_configure_alternate_objects', lambda repo, path: True)

    def fake_restore(
        repo: object,
        path: str,
        snapshot: bytes | None,
        refs_to_delete: set[str],
    ) -> object:
        restore_calls.append((snapshot, refs_to_delete))
        return fake_repo

    monkeypatch.setattr(git_service_module, '_restore_temp_fetch_state', fake_restore)
    messages: list[dict[str, object]] = []

    _fetch_remote_worker(
        str(temp_repo_dir),
        'objects',
        'https://example.com/repo.git',
        'feature',
        0,
        None,
        messages.append,
        Event(),
        None,
        'refs/heads/develop',
        '2' * 40,
        True,
        shallow_snapshot,
    )

    assert fetch_calls == [
        (
            [
                '+refs/heads/develop:refs/heads/develop',
                '+refs/heads/feature:refs/heads/feature',
            ],
            0,
        ),
        (['+refs/heads/feature:refs/heads/feature'], 1),
    ]
    assert restore_calls == [
        (
            shallow_snapshot,
            {'refs/heads/develop', 'refs/heads/feature'},
        )
    ]
    assert messages[-1] == {
        'type': 'result',
        'success': True,
        'depth': 1,
        'shallow_authoritative': True,
    }


def _create_import_repositories(
    tmp_path: Path,
) -> tuple[Path, Path, pygit2.Oid, pygit2.Oid, bytes]:
    source_path = tmp_path / 'source.git'
    source_repo = pygit2.init_repository(str(source_path), bare=True)
    root_oid = _create_commit(source_repo, 'refs/heads/base', 'root', [])
    tip_oid = _create_commit(source_repo, 'refs/heads/main', 'tip', [root_oid])
    shallow_snapshot = f'{root_oid}\n'.encode('ascii')
    (Path(source_repo.path) / 'shallow').write_bytes(shallow_snapshot)
    source_repo.free()

    target_path = tmp_path / 'target'
    target_repo = pygit2.init_repository(str(target_path))
    seed_remote = target_repo.remotes.create('seed', source_path.resolve().as_uri())
    seed_remote.fetch(
        refspecs=['+refs/heads/base:refs/remotes/origin/main'],
        depth=0,
    )
    target_repo.remotes.delete('seed')
    (Path(target_repo.path) / 'shallow').write_bytes(shallow_snapshot)
    target_repo.free()
    return source_path, target_path, root_oid, tip_oid, shallow_snapshot


def test_import_refreshes_repository_before_history_walk(tmp_path: Path) -> None:
    source_path, target_path, root_oid, tip_oid, shallow_snapshot = (
        _create_import_repositories(tmp_path)
    )
    git_service = _create_service(target_path, 'main')
    old_repo = git_service._open_repo()

    git_service._import_fetch_result(
        str(source_path),
        None,
        0.0,
        1.0,
        original_shallow_snapshot=shallow_snapshot,
        shallow_authoritative=True,
    )

    refreshed_repo = git_service._open_repo()
    assert refreshed_repo is not old_repo
    assert refreshed_repo.references['refs/remotes/origin/main'].target == tip_oid
    assert _read_shallow_snapshot(Path(refreshed_repo.path) / 'shallow') == shallow_snapshot
    assert [commit.id for commit in refreshed_repo.walk(tip_oid)] == [tip_oid, root_oid]


def test_import_updates_configured_primary_branch_reference(tmp_path: Path) -> None:
    source_path = tmp_path / 'source.git'
    source_repo = pygit2.init_repository(str(source_path), bare=True)
    primary_oid = _create_commit(source_repo, 'refs/heads/develop', 'develop', [])
    feature_oid = _create_commit(
        source_repo,
        'refs/heads/feature',
        'feature',
        [primary_oid],
    )
    source_repo.free()

    target_path = tmp_path / 'target'
    pygit2.init_repository(str(target_path))
    git_service = _create_service(
        target_path,
        'feature',
        primary_branch='develop',
    )

    git_service._import_fetch_result(
        str(source_path),
        None,
        0.0,
        1.0,
        import_primary_branch=True,
    )

    repo = git_service._open_repo()
    assert repo.references['refs/remotes/origin/develop'].target == primary_oid
    assert repo.references['refs/remotes/origin/feature'].target == feature_oid


def test_import_failure_restores_shallow_and_references(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path, target_path, root_oid, _tip_oid, shallow_snapshot = (
        _create_import_repositories(tmp_path)
    )
    git_service = _create_service(target_path, 'main')
    monkeypatch.setattr(
        git_service_module,
        '_sync_shallow_file',
        lambda *args: (_ for _ in ()).throw(RuntimeError('shallow write failed')),
    )

    with pytest.raises(RuntimeError, match='shallow write failed'):
        git_service._import_fetch_result(
            str(source_path),
            None,
            0.0,
            1.0,
            original_shallow_snapshot=shallow_snapshot,
            shallow_authoritative=True,
        )

    restored_repo = git_service._open_repo()
    assert restored_repo.references['refs/remotes/origin/main'].target == root_oid
    assert _read_shallow_snapshot(Path(restored_repo.path) / 'shallow') == shallow_snapshot
    assert all(
        not remote_name.startswith('one-dragon-fetch-')
        for remote_name in restored_repo.remotes.names()
    )


def test_git_daemon_incremental_fetch_keeps_primary_shallow_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server_root = tmp_path / 'server'
    source_path = server_root / 'repo.git'
    work_path = tmp_path / 'work'
    server_root.mkdir()
    source_path.mkdir()
    work_path.mkdir()
    _git(source_path, 'init', '--bare')
    _git(work_path, 'init')
    _git(work_path, 'config', 'user.name', 'test')
    _git(work_path, 'config', 'user.email', 'test@example.com')
    (work_path / 'README.md').write_text('develop-1\n', encoding='utf-8')
    _git(work_path, 'add', 'README.md')
    _git(work_path, 'commit', '-m', 'develop-1')
    _git(work_path, 'branch', '-M', 'develop')
    (work_path / 'README.md').write_text('develop-2\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'develop-2')
    _git(work_path, 'remote', 'add', 'origin', str(source_path))
    _git(work_path, 'push', 'origin', 'develop')
    develop_1_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'develop~1'))
    _git(work_path, 'checkout', '-b', 'feature', 'develop~1')
    (work_path / 'README.md').write_text('feature-1\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'feature-1')
    _git(work_path, 'push', 'origin', 'feature')
    _git(work_path, 'tag', 'feature-tip')
    _git(work_path, 'checkout', 'develop')
    _git(work_path, 'tag', 'develop-tip')
    _git(work_path, 'push', 'origin', 'refs/tags/feature-tip', 'refs/tags/develop-tip')
    _git(work_path, 'checkout', 'feature')

    target_path = tmp_path / 'target'
    pygit2.init_repository(str(target_path))
    git_service = _create_service(
        target_path,
        'develop',
        primary_branch='develop',
    )
    monkeypatch.setattr(
        git_service_module.os_utils,
        'get_path_under_work_dir',
        lambda *sub_paths: str((tmp_path / 'runtime').joinpath(*sub_paths)),
    )

    with _serve_git_daemon(server_root) as remote_url:
        git_service._fetch_remote_once(remote_url, None, 0.0, 1.0)
        repo = git_service._open_repo()
        primary_oid = repo.references['refs/remotes/origin/develop'].target
        assert 'refs/tags/develop-tip' not in repo.references
        assert 'refs/tags/feature-tip' not in repo.references
        repo.references.create('refs/heads/develop', primary_oid, force=True)

        git_service.env_config.git_branch = 'feature'
        git_service._fetch_remote_once(remote_url, None, 0.0, 1.0)
        repo = git_service._open_repo()
        feature_oid = repo.references['refs/remotes/origin/feature'].target
        repo.references.create('refs/heads/feature', feature_oid, force=True)
        shallow_oids = set(
            _parse_shallow_snapshot(
                _read_shallow_snapshot(Path(repo.path) / 'shallow')
            )
        )
        assert str(primary_oid) in shallow_oids
        assert [commit.id for commit in repo.walk(feature_oid)] == [
            feature_oid,
            develop_1_oid,
        ]

        (work_path / 'README.md').write_text('feature-2\n', encoding='utf-8')
        _git(work_path, 'commit', '-am', 'feature-2')
        _git(work_path, 'push', 'origin', 'feature')
        new_feature_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))

        git_service._fetch_remote_once(remote_url, None, 0.0, 1.0)

    repo = git_service._open_repo()
    assert repo.references['refs/remotes/origin/feature'].target == new_feature_oid
    assert 'refs/tags/develop-tip' not in repo.references
    assert 'refs/tags/feature-tip' not in repo.references
    final_shallow_oids = set(
        _parse_shallow_snapshot(
            _read_shallow_snapshot(Path(repo.path) / 'shallow')
        )
    )
    assert str(primary_oid) in final_shallow_oids
    assert [commit.id for commit in repo.walk(new_feature_oid)] == [
        new_feature_oid,
        feature_oid,
        develop_1_oid,
    ]


def test_git_daemon_repairs_primary_branch_gap_with_single_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server_root = tmp_path / 'server'
    source_path = server_root / 'repo.git'
    work_path = tmp_path / 'work'
    server_root.mkdir()
    source_path.mkdir()
    work_path.mkdir()
    _git(source_path, 'init', '--bare')
    _git(work_path, 'init')
    _git(work_path, 'config', 'user.name', 'test')
    _git(work_path, 'config', 'user.email', 'test@example.com')
    (work_path / 'README.md').write_text('root\n', encoding='utf-8')
    _git(work_path, 'add', 'README.md')
    _git(work_path, 'commit', '-m', 'root')
    _git(work_path, 'branch', '-M', 'main')
    root_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    (work_path / 'README.md').write_text('first\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'first')
    first_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    _git(work_path, 'checkout', '-b', 'side', 'main~1')
    (work_path / 'SIDE.md').write_text('side\n', encoding='utf-8')
    _git(work_path, 'add', 'SIDE.md')
    _git(work_path, 'commit', '-m', 'side')
    side_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    _git(work_path, 'checkout', 'main')
    _git(work_path, 'merge', 'side', '--no-edit', '-m', 'merge side')
    merge_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    (work_path / 'README.md').write_text('after\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'after')
    after_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    (work_path / 'README.md').write_text('tip-main\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'tip-main')
    tip_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    _git(work_path, 'checkout', '-b', 'feature')
    (work_path / 'README.md').write_text('feature-1\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'feature-1')
    feature_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    _git(work_path, 'checkout', 'main')
    _git(work_path, 'tag', 'unrelated-tag')
    _git(
        work_path,
        'remote',
        'add',
        'origin',
        str(source_path),
    )
    _git(
        work_path,
        'push',
        'origin',
        'main',
        'feature',
        'refs/tags/unrelated-tag',
    )

    target_path = tmp_path / 'target'
    pygit2.init_repository(str(target_path))
    git_service = _create_service(target_path, 'feature', primary_branch='main')
    _git(target_path, 'remote', 'add', 'origin', str(source_path))
    _git(target_path, 'fetch', '--depth=3', '--no-tags', 'origin', 'main')
    shallow_path = Path(target_path) / '.git' / 'shallow'
    assert _parse_shallow_snapshot(shallow_path.read_bytes()) == [str(merge_oid)]
    shallow_path.unlink()
    monkeypatch.setattr(
        git_service_module.os_utils,
        'get_path_under_work_dir',
        lambda *sub_paths: str((tmp_path / 'runtime').joinpath(*sub_paths)),
    )

    with _serve_git_daemon(server_root) as remote_url:
        git_service._fetch_remote_once(remote_url, None, 0.0, 1.0)

    repo = git_service._open_repo()
    assert repo.references['refs/remotes/origin/main'].target == tip_oid
    assert repo.references['refs/remotes/origin/feature'].target == feature_oid
    assert 'refs/tags/unrelated-tag' not in repo.references
    assert _parse_shallow_snapshot(shallow_path.read_bytes()) == [str(after_oid)]
    assert [commit.id for commit in repo.walk(feature_oid)] == [
        feature_oid,
        tip_oid,
        after_oid,
    ]
    with pytest.raises(KeyError):
        repo[first_oid]
    with pytest.raises(KeyError):
        repo[root_oid]


def test_git_daemon_rebuilds_malformed_repository_as_shallow_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server_root = tmp_path / 'server'
    source_path = server_root / 'repo.git'
    work_path = tmp_path / 'work'
    server_root.mkdir()
    source_path.mkdir()
    work_path.mkdir()
    _git(source_path, 'init', '--bare')
    _git(work_path, 'init')
    _git(work_path, 'config', 'user.name', 'test')
    _git(work_path, 'config', 'user.email', 'test@example.com')
    (work_path / 'README.md').write_text('root\n', encoding='utf-8')
    _git(work_path, 'add', 'README.md')
    _git(work_path, 'commit', '-m', 'root')
    _git(work_path, 'branch', '-M', 'main')
    root_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    (work_path / 'README.md').write_text('tip\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'tip')
    tip_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    _git(work_path, 'tag', 'main-tip')
    _git(work_path, 'remote', 'add', 'origin', str(source_path))
    _git(work_path, 'push', 'origin', 'main', 'refs/tags/main-tip')

    target_path = tmp_path / 'target'
    old_repo = pygit2.init_repository(str(target_path))
    malformed_shallow = b'invalid\r\n'
    (Path(old_repo.path) / 'shallow').write_bytes(malformed_shallow)
    old_repo.free()
    git_service = _create_service(target_path, 'main')
    monkeypatch.setattr(
        git_service_module.os_utils,
        'get_path_under_work_dir',
        lambda *sub_paths: str((tmp_path / 'runtime').joinpath(*sub_paths)),
    )
    monkeypatch.setattr(git_service, '_restore_origin', lambda: True)

    with _serve_git_daemon(server_root) as remote_url:
        candidate = SimpleNamespace(
            config_item=SimpleNamespace(ui_text='daemon'),
            url=remote_url,
        )
        monkeypatch.setattr(
            git_service,
            '_get_repository_candidates',
            lambda: [(candidate, remote_url)],
        )
        status, _ = git_service._rebuild_repository(None)

    assert status is GitSyncStatus.SUCCESS
    repo = git_service._open_repo()
    assert repo.head.target == tip_oid
    assert 'refs/tags/main-tip' not in repo.references
    assert set(
        _parse_shallow_snapshot(
            _read_shallow_snapshot(Path(repo.path) / 'shallow')
        )
    ) == {str(tip_oid)}
    with pytest.raises(KeyError):
        repo[root_oid]
    backup_dirs = list(target_path.glob('.git.corrupted.*'))
    assert len(backup_dirs) == 1
    assert (backup_dirs[0] / 'shallow').read_bytes() == malformed_shallow


def test_git_daemon_fetches_only_explicit_annotated_tag_at_depth_one(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server_root = tmp_path / 'server'
    source_path = server_root / 'repo.git'
    work_path = tmp_path / 'work'
    server_root.mkdir()
    source_path.mkdir()
    work_path.mkdir()
    _git(source_path, 'init', '--bare')
    _git(work_path, 'init')
    _git(work_path, 'config', 'user.name', 'test')
    _git(work_path, 'config', 'user.email', 'test@example.com')
    (work_path / 'README.md').write_text('root\n', encoding='utf-8')
    _git(work_path, 'add', 'README.md')
    _git(work_path, 'commit', '-m', 'root')
    _git(work_path, 'branch', '-M', 'main')
    root_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    (work_path / 'README.md').write_text('tip\n', encoding='utf-8')
    _git(work_path, 'commit', '-am', 'tip')
    tip_oid = pygit2.Oid(hex=_git(work_path, 'rev-parse', 'HEAD'))
    _git(work_path, 'tag', '-a', 'v1.0.0', '-m', 'release')
    _git(work_path, 'tag', 'peer-tag')
    _git(work_path, 'remote', 'add', 'origin', str(source_path))
    _git(
        work_path,
        'push',
        'origin',
        'main',
        'refs/tags/v1.0.0',
        'refs/tags/peer-tag',
    )

    target_path = tmp_path / 'target'
    pygit2.init_repository(str(target_path))
    git_service = _create_service(target_path, 'main')
    monkeypatch.setattr(
        git_service_module.os_utils,
        'get_path_under_work_dir',
        lambda *sub_paths: str((tmp_path / 'runtime').joinpath(*sub_paths)),
    )

    with _serve_git_daemon(server_root) as remote_url:
        git_service._fetch_remote_once(remote_url, None, 0.0, 1.0, 'v1.0.0')

    repo = git_service._open_repo()
    tag_object = repo.revparse_single('refs/tags/v1.0.0')
    tag_commit = tag_object.peel(pygit2.Commit)
    assert tag_commit.id == tip_oid
    assert repo.references['refs/remotes/origin/main'].target == tip_oid
    assert 'refs/tags/peer-tag' not in repo.references
    assert set(
        _parse_shallow_snapshot(
            _read_shallow_snapshot(Path(repo.path) / 'shallow')
        )
    ) == {str(tip_oid)}
    with pytest.raises(KeyError):
        repo[root_oid]
