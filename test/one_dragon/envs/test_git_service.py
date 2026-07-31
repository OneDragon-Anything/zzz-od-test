"""测试 GitService 的拉取进度回调。"""

import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pygit2
import pytest

import one_dragon.envs.git_service as git_service_module
from one_dragon.envs.env_config import EnvConfig, ProxyTypeEnum
from one_dragon.envs.git_service import (
    GitService,
    GitSyncStatus,
    _cleanup_stale_fetch_repositories,
    _configure_alternate_objects,
    _fetch_remote_worker,
    _FetchProgressRemoteCallbacks,
    _get_repository_objects_path,
    _remove_temp_repo,
    _sync_shallow_file,
)
from one_dragon.envs.repo_config import RepoConfig, RepositoryItem

GITHUB_REPOSITORY = RepositoryItem(
    repository_id='github',
    label='GitHub',
    url='https://github.example/repo.git',
    use_proxy=True,
)
CNB_REPOSITORY = RepositoryItem(
    repository_id='cnb',
    label='CNB',
    url='https://cnb.example/repo.git',
    use_proxy=False,
)
GITEE_REPOSITORY = RepositoryItem(
    repository_id='gitee',
    label='Gitee',
    url='https://gitee.example/repo.git',
    use_proxy=False,
)


def create_repo_config() -> SimpleNamespace:
    repositories = (GITHUB_REPOSITORY, CNB_REPOSITORY, GITEE_REPOSITORY)
    return SimpleNamespace(
        repositories=repositories,
        primary_repository=GITHUB_REPOSITORY,
        find_repository=lambda value: next(
            (
                repository
                for repository in repositories
                if value in (repository.repository_id, repository.label, repository.url)
            ),
            None,
        ),
    )


def test_env_config_proxy_type_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    env_config = EnvConfig.__new__(EnvConfig)
    monkeypatch.setattr(env_config, 'get', lambda key, default=None: default)

    assert env_config.proxy_type == ProxyTypeEnum.NONE.value.value


def test_env_config_repository_url_reads_new_value(monkeypatch: pytest.MonkeyPatch) -> None:
    env_config = EnvConfig.__new__(EnvConfig)
    values = {'repository_url': 'https://cnb.example/repo.git'}
    monkeypatch.setattr(env_config, 'get', lambda key, default=None: values.get(key, default))

    assert env_config.repository_url == 'https://cnb.example/repo.git'


def test_env_config_repository_url_ignores_legacy_value(monkeypatch: pytest.MonkeyPatch) -> None:
    env_config = EnvConfig.__new__(EnvConfig)
    values = {'repository_type': 'CNB'}
    monkeypatch.setattr(env_config, 'get', lambda key, default=None: values.get(key, default))

    assert env_config.repository_url == RepoConfig.AUTO_REPOSITORY_VALUE


def test_env_config_empty_repository_url_uses_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    env_config = EnvConfig.__new__(EnvConfig)
    monkeypatch.setattr(env_config, 'get', lambda key, default=None: '' if key == 'repository_url' else default)

    assert env_config.repository_url == RepoConfig.AUTO_REPOSITORY_VALUE


def test_env_config_last_repository_url_defaults_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    env_config = EnvConfig.__new__(EnvConfig)
    monkeypatch.setattr(env_config, 'get', lambda key, default=None: default)

    assert env_config.last_repository_url == ''


def test_remove_temp_repo_handles_readonly_pack_files(tmp_path: Path) -> None:
    temp_repo_dir = tmp_path / 'fetch_test'
    pack_path = temp_repo_dir / 'objects' / 'pack' / 'test.pack'
    pack_path.parent.mkdir(parents=True)
    pack_path.write_bytes(b'pack')
    pack_path.chmod(0o444)

    _remove_temp_repo(str(temp_repo_dir))

    assert not temp_repo_dir.exists()


def test_remove_temp_repo_defers_windows_busy_pack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = PermissionError('busy')
    error.winerror = 32
    info_messages: list[str] = []
    warning_messages: list[str] = []
    monkeypatch.setattr(git_service_module.sys, 'platform', 'win32')
    monkeypatch.setattr(git_service_module.shutil, 'rmtree', lambda *args, **kwargs: (_ for _ in ()).throw(error))
    monkeypatch.setattr(git_service_module.log, 'info', info_messages.append)
    monkeypatch.setattr(
        git_service_module.log,
        'warning',
        lambda message, **kwargs: warning_messages.append(message),
    )

    _remove_temp_repo('fetch_busy')

    assert info_messages == ['Git fetch 临时仓库仍被占用，将在下次启动时清理: fetch_busy']
    assert warning_messages == []


def test_cleanup_stale_fetch_repositories_removes_dead_and_legacy_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dead_repo = tmp_path / 'fetch_123_dead'
    active_repo = tmp_path / 'fetch_456_active'
    legacy_repo = tmp_path / 'fetch_old'
    unrelated_dir = tmp_path / 'keep'
    for directory in (dead_repo, active_repo, legacy_repo, unrelated_dir):
        directory.mkdir()
    monkeypatch.setattr(git_service_module, '_is_process_running', lambda process_id: process_id == 456)

    _cleanup_stale_fetch_repositories(tmp_path)

    assert not dead_repo.exists()
    assert active_repo.exists()
    assert not legacy_repo.exists()
    assert unrelated_dir.exists()


def test_cleanup_stale_fetch_repositories_runs_once_per_process_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cleanup_calls: list[Path] = []
    resolved_root = tmp_path.resolve()
    git_service_module._fetch_temp_cleanup_roots.discard(resolved_root)
    monkeypatch.setattr(
        git_service_module,
        '_cleanup_stale_fetch_repositories',
        cleanup_calls.append,
    )

    git_service_module._cleanup_stale_fetch_repositories_once(tmp_path)
    git_service_module._cleanup_stale_fetch_repositories_once(tmp_path)

    assert cleanup_calls == [resolved_root]


def test_repository_objects_path_handles_linked_worktree(tmp_path: Path) -> None:
    common_git_dir = tmp_path / 'common.git'
    worktree_git_dir = common_git_dir / 'worktrees' / 'feature'
    (common_git_dir / 'objects').mkdir(parents=True)
    worktree_git_dir.mkdir(parents=True)
    (worktree_git_dir / 'commondir').write_text('../..\n', encoding='utf-8')

    repo = SimpleNamespace(path=str(worktree_git_dir))

    assert _get_repository_objects_path(repo) == common_git_dir / 'objects'


def test_sync_shallow_file_preserves_lf_and_repository_reopens(tmp_path: Path) -> None:
    temp_repo_dir = tmp_path / 'temp'
    temp_repo_dir.mkdir()
    shallow_bytes = b'5d5ef39523c737d7d0b16d00dd91b88a7a0bff4a\n'
    (temp_repo_dir / 'shallow').write_bytes(shallow_bytes)
    target_path = tmp_path / 'target'
    repo = pygit2.init_repository(str(target_path))

    _sync_shallow_file(repo, str(temp_repo_dir))

    target_shallow = Path(repo.path) / 'shallow'
    assert target_shallow.read_bytes() == shallow_bytes
    pygit2.Repository(str(target_path))


def test_open_repo_does_not_modify_existing_crlf_shallow(tmp_path: Path) -> None:
    target_path = tmp_path / 'target'
    repo = pygit2.init_repository(str(target_path))
    shallow_path = Path(repo.path) / 'shallow'
    shallow_bytes = b'5d5ef39523c737d7d0b16d00dd91b88a7a0bff4a\r\n'
    shallow_path.write_bytes(shallow_bytes)
    git_service = GitService(
        SimpleNamespace(),
        SimpleNamespace(),
        create_repo_config(),
        repo_dir=str(target_path),
    )

    with pytest.raises(pygit2.GitError):
        git_service._open_repo()

    assert shallow_path.read_bytes() == shallow_bytes


def test_configure_alternate_objects_writes_source_object_directory(tmp_path: Path) -> None:
    source_objects_dir = tmp_path / 'source' / 'objects'
    source_objects_dir.mkdir(parents=True)
    temp_repo = pygit2.init_repository(str(tmp_path / 'temp'), bare=True)

    assert _configure_alternate_objects(temp_repo, str(source_objects_dir)) is True
    alternates_path = Path(temp_repo.path) / 'objects' / 'info' / 'alternates'
    assert alternates_path.read_text(encoding='utf-8') == f'{source_objects_dir.resolve()}\n'



def test_fetch_worker_uses_alternates_for_depth_zero(tmp_path: Path) -> None:
    source_path = tmp_path / 'source'
    source_repo = pygit2.init_repository(str(source_path), bare=True)
    tree_builder = source_repo.TreeBuilder()
    blob_id = source_repo.create_blob(b'hello')
    tree_builder.insert('README.md', blob_id, pygit2.GIT_FILEMODE_BLOB)
    tree_id = tree_builder.write()
    signature = pygit2.Signature('test', 'test@example.com')
    commit_id = source_repo.create_commit(
        'refs/heads/main',
        signature,
        signature,
        'init',
        tree_id,
        [],
    )

    temp_repo_path = tmp_path / 'temp'
    messages: list[dict[str, object]] = []
    abandoned = Event()
    source_objects_path = Path(source_repo.path) / 'objects'

    _fetch_remote_worker(
        str(temp_repo_path),
        str(Path(source_repo.path) / 'objects'),
        source_path.resolve().as_uri(),
        'main',
        0,
        None,
        messages.append,
        abandoned,
    )

    assert messages[-1] == {'type': 'result', 'success': True, 'depth': 0}
    alternates_path = temp_repo_path / 'objects' / 'info' / 'alternates'
    assert alternates_path.read_text(encoding='utf-8') == f'{source_objects_path.resolve()}\n'
    temp_repo = pygit2.Repository(str(temp_repo_path))
    assert temp_repo.references['refs/heads/main'].target == commit_id


@pytest.mark.parametrize(
    ('fetch_error', 'expected_messages'),
    [
        (
            None,
            [
                {'type': 'progress', 'progress': 0.0, 'message': '远程消息: Total 4 (delta 1)'},
                {'type': 'result', 'success': True, 'depth': 1},
            ],
        ),
        (
            RuntimeError('fetch failed'),
            [
                {'type': 'result', 'success': False, 'error': "RuntimeError('fetch failed')"},
            ],
        ),
    ],
)
def test_fetch_worker_flushes_sideband_only_after_success(
    monkeypatch: pytest.MonkeyPatch,
    fetch_error: RuntimeError | None,
    expected_messages: list[dict[str, object]],
) -> None:
    class FakeRemote:
        def fetch(
            self,
            *,
            refspecs: list[str],
            proxy: str | None,
            depth: int,
            callbacks: _FetchProgressRemoteCallbacks,
        ) -> None:
            callbacks.sideband_progress('Total 4 (delta 1)')
            if fetch_error is not None:
                raise fetch_error

    fake_repo = SimpleNamespace(
        remotes=SimpleNamespace(create=lambda name, url: FakeRemote()),
    )
    monkeypatch.setattr(git_service_module, 'init_repository', lambda path, bare: fake_repo)
    messages: list[dict[str, object]] = []

    _fetch_remote_worker(
        'unused',
        None,
        'https://example.com/repo.git',
        'main',
        1,
        None,
        messages.append,
        Event(),
    )

    assert messages == expected_messages


def test_fetch_worker_uses_new_callbacks_after_depth_zero_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRemote:
        def fetch(
            self,
            *,
            refspecs: list[str],
            proxy: str | None,
            depth: int,
            callbacks: _FetchProgressRemoteCallbacks,
        ) -> None:
            if depth == 0:
                callbacks.sideband_progress('Counting objects: 50% (1/')
                raise KeyError('object not found')
            callbacks.sideband_progress('Counting objects: 100% (2/2), done.\n')

    fake_repo = SimpleNamespace(
        remotes=SimpleNamespace(create=lambda name, url: FakeRemote()),
    )
    monkeypatch.setattr(git_service_module, 'init_repository', lambda path, bare: fake_repo)
    monkeypatch.setattr(git_service_module, '_configure_alternate_objects', lambda repo, path: True)
    messages: list[dict[str, object]] = []

    _fetch_remote_worker(
        'unused',
        'objects',
        'https://example.com/repo.git',
        'main',
        0,
        None,
        messages.append,
        Event(),
    )

    assert messages == [
        {
            'type': 'progress',
            'progress': 0.0,
            'message': '远程消息: 统计对象: 100% (2/2), done.',
        },
        {'type': 'result', 'success': True, 'depth': 1},
    ]


class TestFetchProgressRemoteCallbacks:
    """测试 _FetchProgressRemoteCallbacks 的当前行为。

    注意：当前实现中 stage 映射已上移到 GitService._create_fetch_callbacks，
    此处回调只接收 progress_callback，并直接传出原始进度（0.0~1.0）；
    sideband_progress 会拆分服务端用回车或换行发送的进度消息。
    """

    def test_transfer_progress_reports_object_progress_with_percentage(self) -> None:
        events: list[tuple[float, str]] = []
        # 当前构造器只接收 progress_callback，不再接收 stage_start/stage_end
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
        )

        stats = SimpleNamespace(received_objects=3, total_objects=10, received_bytes=4096)
        callbacks.transfer_progress(stats)

        assert len(events) == 1
        progress, message = events[0]
        # 不做 stage 映射，直接传 received/total 原始进度
        assert progress == pytest.approx(0.3)
        assert message == '拉取对象 3/10 (30%)'

    def test_sideband_progress_buffers_split_remote_progress_messages(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
        )

        callbacks.sideband_progress(
            'Enumerating objects: 3843, done.\n'
            'Counting objects: 50% (1922/'
        )

        assert events == [
            (0.0, '远程消息: 枚举对象: 3843, done.'),
        ]

        callbacks.sideband_progress(
            '3843)\r'
            'Counting objects: 100% (3843/3843), done.\n'
            'Compressing objects: 50% (1652/3303)\r'
            'Compressing objects: 100% (3303/3303), done.\n'
        )

        assert events == [
            (0.0, '远程消息: 枚举对象: 3843, done.'),
            (0.0, '远程消息: 统计对象: 50% (1922/3843)'),
            (0.0, '远程消息: 统计对象: 100% (3843/3843), done.'),
            (0.0, '远程消息: 压缩对象: 50% (1652/3303)'),
            (0.0, '远程消息: 压缩对象: 100% (3303/3303), done.'),
        ]

    def test_flush_sideband_progress_outputs_remaining_message_once(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
        )

        callbacks.sideband_progress('Total 3843 (delta 794)')
        assert events == []

        callbacks.flush_sideband_progress()
        callbacks.flush_sideband_progress()

        assert events == [
            (0.0, '远程消息: Total 3843 (delta 794)'),
        ]

    def test_transfer_progress_falls_back_to_received_bytes(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
        )

        stats = SimpleNamespace(received_objects=0, total_objects=0, received_bytes=3 * 1024 * 1024)
        callbacks.transfer_progress(stats)

        assert len(events) == 1
        progress, message = events[0]
        # total_objects 为 0 时进度回退为 0.0，消息用 MB
        assert progress == pytest.approx(0.0)
        assert message == '拉取对象 3.00 MB'

    def test_transfer_progress_deduplicates_identical_messages(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
        )

        stats = SimpleNamespace(received_objects=12, total_objects=12, received_bytes=2048)
        callbacks.transfer_progress(stats)
        callbacks.transfer_progress(stats)

        assert events == [
            (1.0, '拉取对象 12/12 (100%), done.'),
        ]

    def test_transfer_progress_reports_delta_after_objects_are_received(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
            timeout=None,
        )
        timestamps = iter([0.0, 0.0, 0.3, 0.4])
        monkeypatch.setattr(git_service_module.time, 'monotonic', lambda: next(timestamps))

        callbacks.transfer_progress(
            SimpleNamespace(
                received_objects=10,
                total_objects=10,
                total_deltas=2,
                indexed_deltas=0,
                received_bytes=4096,
            )
        )
        callbacks.transfer_progress(
            SimpleNamespace(
                received_objects=10,
                total_objects=10,
                total_deltas=2,
                indexed_deltas=1,
                received_bytes=4096,
            )
        )
        callbacks.transfer_progress(
            SimpleNamespace(
                received_objects=10,
                total_objects=10,
                total_deltas=2,
                indexed_deltas=2,
                received_bytes=4096,
            )
        )

        assert events == [
            (1.0, '拉取对象 10/10 (100%), done.'),
            (0.0, '处理增量 0/2 (0%)'),
            (0.5, '处理增量 1/2 (50%)'),
            (1.0, '处理增量 2/2 (100%), done.'),
        ]

    def test_update_tips_flushes_sideband_before_reference_message(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
        )

        callbacks.sideband_progress('remote progress')
        callbacks.update_tips('refs/remotes/origin/main', None, None)

        assert events == [
            (0.0, '远程消息: remote progress'),
            (0.0, '更新引用: refs/remotes/origin/main'),
        ]

    def test_timeout_is_raised_from_callback(self) -> None:
        callbacks = _FetchProgressRemoteCallbacks(lambda progress, message: None, timeout=0)

        with pytest.raises(TimeoutError):
            callbacks.transfer_progress(SimpleNamespace(received_objects=1, total_objects=1, received_bytes=0))

    @pytest.fixture
    def git_service(self) -> GitService:
        project_config = SimpleNamespace()
        env_config = SimpleNamespace(
            git_branch='main',
            git_remote='origin',
            repository_url=GITHUB_REPOSITORY.url,
            last_repository_url='',
            is_gh_proxy=False,
            gh_proxy_url='',
            is_personal_proxy=False,
            personal_proxy='',
        )
        repo_config = create_repo_config()
        return GitService(project_config, env_config, repo_config, repo_dir='.')

    def test_fetch_remote_reports_progress_and_success(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        repo = SimpleNamespace(references={})
        events: list[tuple[float, str]] = []
        imported: list[str] = []

        def fake_worker(*args: object) -> None:
            message_callback = args[6]
            message_callback({'type': 'progress', 'progress': 0.5, 'message': '拉取对象 2/4 (50%)'})
            message_callback({'type': 'result', 'success': True})

        monkeypatch.setattr(git_service_module, '_fetch_remote_worker', fake_worker)
        monkeypatch.setattr(
            git_service_module.os_utils,
            'get_path_under_work_dir',
            lambda *sub_paths: str(tmp_path.joinpath(*sub_paths)),
        )
        monkeypatch.setattr(git_service, '_open_repo', lambda: repo)
        monkeypatch.setattr(
            git_service,
            '_import_fetch_result',
            lambda temp_repo_dir, progress_callback, stage_start, stage_end, tag_name: imported.append(temp_repo_dir),
        )

        git_service._fetch_remote_once(
            GITHUB_REPOSITORY.url,
            lambda progress, message: events.append((progress, message)),
            0.2,
            0.4,
        )

        assert imported
        assert Path(imported[0]).name.startswith(f'fetch_{git_service_module.os.getpid()}_')
        assert events[0][0] == pytest.approx(0.3)
        assert events[0][1] == '拉取对象 2/4 (50%)'

    def test_fetch_remote_imports_successful_worker_result(
        self,
        tmp_path: Path,
    ) -> None:
        temp_path = tmp_path
        source_path = temp_path / 'source'
        target_path = temp_path / 'target'
        source_repo = pygit2.init_repository(str(source_path), bare=True)
        commit_tree = source_repo.TreeBuilder()
        blob_id = source_repo.create_blob(b'hello')
        commit_tree.insert('README.md', blob_id, pygit2.GIT_FILEMODE_BLOB)
        tree_id = commit_tree.write()
        signature = pygit2.Signature('test', 'test@example.com')
        commit_id = source_repo.create_commit(
            'refs/heads/main',
            signature,
            signature,
            'init',
            tree_id,
            [],
        )
        target_repo = pygit2.init_repository(str(target_path))
        target_tree = target_repo.TreeBuilder()
        target_blob_id = target_repo.create_blob(b'hello')
        target_tree.insert('README.md', target_blob_id, pygit2.GIT_FILEMODE_BLOB)
        target_tree_id = target_tree.write()
        target_commit_id = target_repo.create_commit(
            'refs/heads/main',
            signature,
            signature,
            'init',
            target_tree_id,
            [],
        )
        assert target_commit_id == commit_id
        env_config = SimpleNamespace(
            git_branch='main',
            git_remote='origin',
            repository_url=GITHUB_REPOSITORY.url,
            last_repository_url='',
            is_gh_proxy=False,
            gh_proxy_url='',
            is_personal_proxy=False,
            personal_proxy='',
        )
        git_service = GitService(
            SimpleNamespace(),
            env_config,
            create_repo_config(),
            repo_dir=str(target_path),
        )

        git_service._fetch_remote_once(source_path.resolve().as_uri(), None, 0.0, 1.0)

        target_repo = pygit2.Repository(str(target_path))
        remote_ref = target_repo.references['refs/remotes/origin/main']
        assert remote_ref.target == commit_id
        assert list(target_repo.remotes.names()) == []

    def test_import_fetch_result_uses_annotated_tag_as_remote_branch(
        self,
        tmp_path: Path,
    ) -> None:
        source_path = tmp_path / 'source'
        target_path = tmp_path / 'target'
        source_repo = pygit2.init_repository(str(source_path), bare=True)
        tree_builder = source_repo.TreeBuilder()
        blob_id = source_repo.create_blob(b'release')
        tree_builder.insert('README.md', blob_id, pygit2.GIT_FILEMODE_BLOB)
        tree_id = tree_builder.write()
        signature = pygit2.Signature('test', 'test@example.com')
        commit_id = source_repo.create_commit(
            'refs/heads/main',
            signature,
            signature,
            'release',
            tree_id,
            [],
        )
        source_repo.create_tag(
            'v1.0.0',
            commit_id,
            pygit2.enums.ObjectType.COMMIT,
            signature,
            'v1.0.0',
        )
        pygit2.init_repository(str(target_path))
        env_config = SimpleNamespace(
            git_branch='main',
            git_remote='origin',
            repository_url=GITHUB_REPOSITORY.url,
            last_repository_url='',
            is_gh_proxy=False,
            gh_proxy_url='',
            is_personal_proxy=False,
            personal_proxy='',
        )
        git_service = GitService(
            SimpleNamespace(),
            env_config,
            create_repo_config(),
            repo_dir=str(target_path),
        )

        git_service._import_fetch_result(
            str(source_path),
            None,
            0.0,
            1.0,
            'v1.0.0',
        )

        target_repo = pygit2.Repository(str(target_path))
        assert target_repo.references['refs/remotes/origin/main'].target == commit_id
        assert target_repo.revparse_single('refs/tags/v1.0.0').peel(pygit2.Commit).id == commit_id
        assert 'refs/heads/main' not in target_repo.references

    def run_timed_fetch_worker(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        scheduled_messages: list[tuple[float, dict[str, object]]],
        initial_timeout: float = 0.05,
        idle_timeout: float = 0.08,
        total_timeout: float = 0.2,
    ) -> tuple[Exception | None, float, bool, bool]:
        imported = False
        release_worker = Event()
        worker_finished = Event()
        abandoned_holder: list[Event] = []

        def fake_worker(*args: object) -> None:
            message_callback = args[6]
            abandoned = args[7]
            assert callable(message_callback)
            assert isinstance(abandoned, Event)
            abandoned_holder.append(abandoned)
            started_at = time.monotonic()
            try:
                for scheduled_at, message in scheduled_messages:
                    remaining = scheduled_at - (time.monotonic() - started_at)
                    if remaining > 0:
                        time.sleep(remaining)
                    message_callback(message)
                if not any(message.get('type') == 'result' for _, message in scheduled_messages):
                    release_worker.wait(timeout=1)
            finally:
                worker_finished.set()

        def fake_import(
            temp_repo_dir: str,
            progress_callback: object,
            stage_start: float,
            stage_end: float,
            tag_name: str | None,
        ) -> None:
            nonlocal imported
            imported = True

        monkeypatch.setattr(git_service_module, 'REMOTE_FETCH_INITIAL_TIMEOUT', initial_timeout)
        monkeypatch.setattr(git_service_module, 'REMOTE_FETCH_IDLE_TIMEOUT', idle_timeout)
        monkeypatch.setattr(git_service_module, 'REMOTE_FETCH_TIMEOUT', total_timeout)
        monkeypatch.setattr(git_service_module, '_fetch_remote_worker', fake_worker)
        monkeypatch.setattr(
            git_service_module.os_utils,
            'get_path_under_work_dir',
            lambda *sub_paths: str(tmp_path.joinpath(*sub_paths)),
        )
        monkeypatch.setattr(git_service, '_open_repo', lambda: SimpleNamespace(references={}))
        monkeypatch.setattr(git_service, '_import_fetch_result', fake_import)

        started_at = time.monotonic()
        error: Exception | None = None
        try:
            git_service._fetch_remote_once('https://example.com/repo.git', None, 0.0, 1.0)
        except Exception as caught:
            error = caught
        elapsed = time.monotonic() - started_at

        release_worker.set()
        worker_finished.wait(timeout=1)
        return error, elapsed, bool(abandoned_holder and abandoned_holder[0].is_set()), imported

    def test_fetch_remote_initial_message_timeout(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        error, elapsed, abandoned, imported = self.run_timed_fetch_worker(
            git_service,
            monkeypatch,
            tmp_path,
            [],
        )

        assert isinstance(error, TimeoutError)
        assert str(error) == 'Git 远程拉取首条消息超过 0.05 秒'
        assert elapsed >= 0.05
        assert abandoned is True
        assert imported is False

    def test_fetch_remote_idle_message_timeout(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        error, elapsed, abandoned, imported = self.run_timed_fetch_worker(
            git_service,
            monkeypatch,
            tmp_path,
            [(0.02, {'type': 'progress', 'progress': 0.1, 'message': '开始'})],
        )

        assert isinstance(error, TimeoutError)
        assert str(error) == 'Git 远程拉取消息空闲超过 0.08 秒'
        assert elapsed >= 0.1
        assert abandoned is True
        assert imported is False

    def test_fetch_remote_active_worker_still_hits_total_timeout(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        progress_messages = [
            (timestamp, {'type': 'progress', 'progress': timestamp / 0.12, 'message': str(timestamp)})
            for timestamp in (0.03, 0.06, 0.09)
        ]
        error, elapsed, abandoned, imported = self.run_timed_fetch_worker(
            git_service,
            monkeypatch,
            tmp_path,
            progress_messages,
            idle_timeout=0.05,
            total_timeout=0.12,
        )

        assert isinstance(error, TimeoutError)
        assert str(error) == 'Git 远程拉取超过 0.12 秒'
        assert elapsed >= 0.12
        assert abandoned is True
        assert imported is False

    def test_fetch_remote_active_worker_can_finish_before_total_timeout(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        messages = [
            (0.02, {'type': 'progress', 'progress': 0.2, 'message': '20%'}),
            (0.04, {'type': 'progress', 'progress': 0.6, 'message': '60%'}),
            (0.06, {'type': 'result', 'success': True}),
        ]
        error, _elapsed, abandoned, imported = self.run_timed_fetch_worker(
            git_service,
            monkeypatch,
            tmp_path,
            messages,
            idle_timeout=0.05,
            total_timeout=0.12,
        )

        assert error is None
        assert abandoned is False
        assert imported is True

    def test_fetch_remote_timeout_abandons_worker_and_falls_back(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        repo = SimpleNamespace(references={})
        imported: list[str] = []
        abandoned_states: list[Event] = []
        worker_count = 0

        def fake_worker(*args: object) -> None:
            nonlocal worker_count
            worker_count += 1
            message_callback = args[6]
            abandoned = args[7]
            assert callable(message_callback)
            assert isinstance(abandoned, Event)
            abandoned_states.append(abandoned)
            if worker_count == 1:
                abandoned.wait(timeout=1)
            else:
                message_callback({'type': 'result', 'success': True})

        monkeypatch.setattr(git_service_module, 'REMOTE_FETCH_INITIAL_TIMEOUT', 0.02)
        monkeypatch.setattr(git_service_module, 'REMOTE_FETCH_IDLE_TIMEOUT', 0.02)
        monkeypatch.setattr(git_service_module, 'REMOTE_FETCH_TIMEOUT', 0.05)
        monkeypatch.setattr(git_service_module, '_fetch_remote_worker', fake_worker)
        monkeypatch.setattr(
            git_service_module.os_utils,
            'get_path_under_work_dir',
            lambda *sub_paths: str(tmp_path.joinpath(*sub_paths)),
        )
        monkeypatch.setattr(git_service, '_open_repo', lambda: repo)
        monkeypatch.setattr(
            git_service,
            '_import_fetch_result',
            lambda temp_repo_dir, progress_callback, stage_start, stage_end, tag_name: imported.append(temp_repo_dir),
        )
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)

        assert git_service._fetch_remote() is True
        assert worker_count == 2
        assert abandoned_states[0].is_set() is True
        assert abandoned_states[1].is_set() is False
        assert len(imported) == 1
        assert repo.references == {}

    def test_repository_candidates_use_preferred_source_first(self, git_service: GitService) -> None:
        candidates = git_service._get_repository_candidates()

        assert candidates == [
            (GITHUB_REPOSITORY, 'https://github.example/repo.git'),
            (CNB_REPOSITORY, 'https://cnb.example/repo.git'),
            (GITEE_REPOSITORY, 'https://gitee.example/repo.git'),
        ]

    def test_restore_origin_uses_raw_github_url(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        restored_urls: list[str] = []
        monkeypatch.setattr(
            git_service,
            '_ensure_remote',
            lambda remote_url=None: restored_urls.append(remote_url) or object(),
        )

        assert git_service._restore_origin() is True
        assert restored_urls == ['https://github.example/repo.git']

    def test_fetch_remote_falls_back_and_restores_origin(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        attempted_urls: list[str] = []

        def fake_fetch(
            repository_url: str,
            progress_callback: object,
            stage_start: float,
            stage_end: float,
            tag_name: str | None,
        ) -> None:
            attempted_urls.append(repository_url)
            if len(attempted_urls) == 1:
                raise TimeoutError('模拟超时')

        restored = False

        def fake_restore() -> bool:
            nonlocal restored
            restored = True
            return True

        monkeypatch.setattr(git_service, '_fetch_remote_once', fake_fetch)
        monkeypatch.setattr(git_service, '_restore_origin', fake_restore)

        assert git_service._fetch_remote() is True
        assert attempted_urls == [
            'https://github.example/repo.git',
            'https://cnb.example/repo.git',
        ]
        assert git_service.env_config.last_repository_url == CNB_REPOSITORY.url
        assert restored is True

    def test_successful_fetch_still_fails_when_origin_restore_fails(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(git_service, '_fetch_remote_once', lambda *args: None)
        monkeypatch.setattr(git_service, '_restore_origin', lambda: False)

        assert git_service._fetch_remote() is False

    def test_auto_source_records_successful_repository_when_manifest_rejects_update(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        attempted_urls: list[str] = []
        git_service.env_config.repository_url = RepoConfig.AUTO_REPOSITORY_VALUE
        git_service.env_config.last_repository_url = GITHUB_REPOSITORY.url

        def fake_fetch(
            repository_url: str,
            progress_callback: object,
            stage_start: float,
            stage_end: float,
            tag_name: str | None,
        ) -> None:
            attempted_urls.append(repository_url)
            if repository_url == GITHUB_REPOSITORY.url:
                raise TimeoutError('GitHub 不可用')

        monkeypatch.setattr(git_service, '_fetch_remote_once', fake_fetch)
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)
        monkeypatch.setattr(
            git_service,
            '_check_remote_manifest_compatible',
            lambda: (False, '目标版本的运行环境与当前不兼容'),
        )

        status, message = git_service._fetch_and_checkout_latest_branch()

        assert status is GitSyncStatus.RUNTIME_INCOMPATIBLE
        assert message == '目标版本的运行环境与当前不兼容'
        assert attempted_urls == [GITHUB_REPOSITORY.url, CNB_REPOSITORY.url]
        assert git_service.env_config.last_repository_url == CNB_REPOSITORY.url

    def test_first_clone_returns_runtime_incompatible_before_checkout(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(git_service_module, 'init_repository', lambda path: calls.append('init'))
        monkeypatch.setattr(
            git_service,
            '_fetch_remote',
            lambda progress_callback, stage_start, stage_end, tag_name: calls.append('fetch') is None,
        )
        monkeypatch.setattr(
            git_service,
            '_check_remote_manifest_compatible',
            lambda: (False, '目标版本的运行环境与当前不兼容'),
        )
        monkeypatch.setattr(git_service, '_checkout_branch', lambda: calls.append('checkout') is None)
        monkeypatch.setattr(
            git_service,
            '_sync_with_remote',
            lambda force: (calls.append('sync') is None, ''),
        )

        status, message = git_service._clone_repository()

        assert status is GitSyncStatus.RUNTIME_INCOMPATIBLE
        assert message == '目标版本的运行环境与当前不兼容'
        assert calls == ['init', 'fetch']

    def test_first_clone_uses_builtin_tag_without_manifest_check(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[object] = []
        monkeypatch.setattr(git_service_module, 'init_repository', lambda path: calls.append('init'))
        monkeypatch.setattr(
            git_service,
            '_fetch_remote',
            lambda progress_callback, stage_start, stage_end, tag_name: calls.append(tag_name) or True,
        )
        monkeypatch.setattr(
            git_service,
            '_check_remote_manifest_compatible',
            lambda: (_ for _ in ()).throw(AssertionError('按内置 tag 拉取不应再检查清单')),
        )
        monkeypatch.setattr(git_service, '_checkout_branch', lambda: calls.append('checkout') or True)
        monkeypatch.setattr(
            git_service,
            '_sync_with_remote',
            lambda force: (calls.append(('sync', force)) is None, 'ok'),
        )

        status, message = git_service._clone_repository(initial_tag='v1.0.0')

        assert status is GitSyncStatus.SUCCESS
        assert message == '克隆仓库成功'
        assert calls == ['init', 'v1.0.0', 'checkout', ('sync', True)]

    def test_first_clone_keeps_builtin_code_when_tag_is_unavailable(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(git_service_module, 'init_repository', lambda path: calls.append('init'))
        monkeypatch.setattr(
            git_service,
            '_fetch_remote',
            lambda progress_callback, stage_start, stage_end, tag_name: calls.append(tag_name) or False,
        )
        monkeypatch.setattr(git_service, '_checkout_branch', lambda: calls.append('checkout') is not None)

        status, message = git_service._clone_repository(initial_tag='v1.0.0')

        assert status is GitSyncStatus.BUILTIN_TAG_UNAVAILABLE
        assert message == '未能获取内置版本对应的代码标签 v1.0.0'
        assert calls == ['init', 'v1.0.0']

    def test_fetch_latest_code_retries_builtin_tag_while_local_branch_is_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        repo_path = tmp_path / 'repo'
        pygit2.init_repository(str(repo_path))
        env_config = SimpleNamespace(git_branch='main')
        git_service = GitService(
            SimpleNamespace(),
            env_config,
            create_repo_config(),
            repo_dir=str(repo_path),
        )
        received_tags: list[str | None] = []
        monkeypatch.setattr(
            git_service,
            '_clone_repository',
            lambda progress_callback, initial_tag: (
                received_tags.append(initial_tag)
                or (
                    GitSyncStatus.BUILTIN_TAG_UNAVAILABLE,
                    f'未能获取内置版本对应的代码标签 {initial_tag}',
                )
            ),
        )
        monkeypatch.setattr(
            git_service,
            '_fetch_and_checkout_latest_branch',
            lambda progress_callback: (_ for _ in ()).throw(AssertionError('不得退化到分支更新')),
        )

        first_status, _ = git_service.fetch_latest_code(initial_tag='v1.0.0')
        second_status, _ = git_service.fetch_latest_code(initial_tag='v1.0.0')

        assert first_status is GitSyncStatus.BUILTIN_TAG_UNAVAILABLE
        assert second_status is GitSyncStatus.BUILTIN_TAG_UNAVAILABLE
        assert received_tags == ['v1.0.0', 'v1.0.0']

    def test_fetch_remote_returns_false_when_all_sources_fail(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_fetch(
            repository_url: str,
            progress_callback: object,
            stage_start: float,
            stage_end: float,
            tag_name: str | None,
        ) -> None:
            raise TimeoutError(repository_url)

        monkeypatch.setattr(git_service, '_fetch_remote_once', fake_fetch)
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)
        git_service.env_config.last_repository_url = CNB_REPOSITORY.url

        assert git_service._fetch_remote() is False
        assert git_service.env_config.last_repository_url == CNB_REPOSITORY.url

    def test_auto_source_prioritizes_last_successful_repository(self, git_service: GitService) -> None:
        git_service.env_config.repository_url = RepoConfig.AUTO_REPOSITORY_VALUE
        git_service.env_config.last_repository_url = CNB_REPOSITORY.url

        assert git_service._get_repository_candidates() == [
            (CNB_REPOSITORY, 'https://cnb.example/repo.git'),
            (GITHUB_REPOSITORY, 'https://github.example/repo.git'),
            (GITEE_REPOSITORY, 'https://gitee.example/repo.git'),
        ]

    def test_unknown_configured_repository_resets_to_auto(self, git_service: GitService) -> None:
        git_service.env_config.repository_url = 'https://removed.example/repo.git'
        git_service.env_config.last_repository_url = CNB_REPOSITORY.url

        assert git_service._get_repository_candidates() == [
            (CNB_REPOSITORY, 'https://cnb.example/repo.git'),
            (GITHUB_REPOSITORY, 'https://github.example/repo.git'),
            (GITEE_REPOSITORY, 'https://gitee.example/repo.git'),
        ]
        assert git_service.env_config.repository_url == RepoConfig.AUTO_REPOSITORY_VALUE

    def test_auto_source_ignores_unknown_last_repository(self, git_service: GitService) -> None:
        git_service.env_config.repository_url = RepoConfig.AUTO_REPOSITORY_VALUE
        git_service.env_config.last_repository_url = 'https://removed.example/repo.git'

        assert git_service._get_repository_candidates() == [
            (GITHUB_REPOSITORY, 'https://github.example/repo.git'),
            (CNB_REPOSITORY, 'https://cnb.example/repo.git'),
            (GITEE_REPOSITORY, 'https://gitee.example/repo.git'),
        ]

    def test_preferred_source_is_promoted_by_configured_url(self, git_service: GitService) -> None:
        git_service.env_config.repository_url = GITEE_REPOSITORY.url
        git_service.env_config.last_repository_url = CNB_REPOSITORY.url

        assert git_service._get_repository_candidates() == [
            (GITEE_REPOSITORY, 'https://gitee.example/repo.git'),
            (GITHUB_REPOSITORY, 'https://github.example/repo.git'),
            (CNB_REPOSITORY, 'https://cnb.example/repo.git'),
        ]

    def test_proxy_only_applies_to_enabled_repository(self, git_service: GitService) -> None:
        git_service.env_config.is_gh_proxy = True
        git_service.env_config.gh_proxy_url = 'https://proxy.example'

        assert git_service._get_repository_candidates() == [
            (GITHUB_REPOSITORY, 'https://proxy.example/https://github.example/repo.git'),
            (CNB_REPOSITORY, 'https://cnb.example/repo.git'),
            (GITEE_REPOSITORY, 'https://gitee.example/repo.git'),
        ]

    def test_successful_proxied_fetch_records_raw_repository_url(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        attempted_urls: list[str] = []
        git_service.env_config.repository_url = RepoConfig.AUTO_REPOSITORY_VALUE
        git_service.env_config.is_gh_proxy = True
        git_service.env_config.gh_proxy_url = 'https://proxy.example'
        monkeypatch.setattr(
            git_service,
            '_fetch_remote_once',
            lambda repository_url, progress_callback, stage_start, stage_end, tag_name: attempted_urls.append(
                repository_url
            ),
        )
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)

        assert git_service._fetch_remote() is True
        assert attempted_urls == ['https://proxy.example/https://github.example/repo.git']
        assert git_service.env_config.last_repository_url == GITHUB_REPOSITORY.url

    def test_all_missing_object_failures_trigger_repository_rebuild(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rebuild_calls: list[object] = []

        def missing_object(*args: object) -> None:
            raise KeyError('object not found - no match for id')

        monkeypatch.setattr(git_service, '_fetch_remote_once', missing_object)
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)
        monkeypatch.setattr(
            git_service,
            '_rebuild_repository',
            lambda progress_callback, initial_tag: rebuild_calls.append(progress_callback) is None,
        )

        assert git_service._fetch_remote() is True
        assert rebuild_calls == [None]

    def test_tag_missing_object_rebuild_keeps_initial_tag(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rebuild_calls: list[tuple[object, str | None]] = []

        monkeypatch.setattr(
            git_service,
            '_fetch_remote_once',
            lambda *args: (_ for _ in ()).throw(KeyError('object not found - no match for id')),
        )
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)
        monkeypatch.setattr(
            git_service,
            '_rebuild_repository',
            lambda progress_callback, initial_tag: rebuild_calls.append((progress_callback, initial_tag)) is None,
        )

        assert git_service._fetch_remote(tag_name='v1.0.0') is True
        assert rebuild_calls == [(None, 'v1.0.0')]

    def test_missing_object_failure_rebuilds_when_origin_restore_fails(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rebuild_calls: list[object] = []
        monkeypatch.setattr(
            git_service,
            '_fetch_remote_once',
            lambda *args: (_ for _ in ()).throw(KeyError('object not found - no match for id')),
        )
        monkeypatch.setattr(git_service, '_restore_origin', lambda: False)
        monkeypatch.setattr(
            git_service,
            '_rebuild_repository',
            lambda progress_callback, initial_tag: rebuild_calls.append(progress_callback) is None,
        )

        assert git_service._fetch_remote() is True
        assert rebuild_calls == [None]

    def test_missing_object_and_network_failure_trigger_repository_rebuild(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        attempts = 0
        rebuild_calls: list[object] = []

        def mixed_failure(*args: object) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                raise TimeoutError('模拟超时')
            raise KeyError('object not found - no match for id')

        monkeypatch.setattr(git_service, '_fetch_remote_once', mixed_failure)
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)
        monkeypatch.setattr(
            git_service,
            '_rebuild_repository',
            lambda progress_callback, initial_tag: rebuild_calls.append(progress_callback) is None,
        )

        assert git_service._fetch_remote() is True
        assert rebuild_calls == [None]

    def test_network_failures_do_not_trigger_repository_rebuild(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rebuild_calls: list[object] = []
        monkeypatch.setattr(
            git_service,
            '_fetch_remote_once',
            lambda *args: (_ for _ in ()).throw(RuntimeError('request failed')),
        )
        monkeypatch.setattr(git_service, '_restore_origin', lambda: True)
        monkeypatch.setattr(
            git_service,
            '_rebuild_repository',
            lambda progress_callback, initial_tag: rebuild_calls.append(progress_callback) is None,
        )

        assert git_service._fetch_remote() is False
        assert rebuild_calls == []

    def test_rebuild_repository_skips_repository_with_extra_remote(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        repo_path = tmp_path / 'repo'
        repo = pygit2.init_repository(str(repo_path))
        repo.remotes.create('origin', 'https://origin.example/repo.git')
        repo.remotes.create('upstream', 'https://upstream.example/repo.git')
        git_service = GitService(
            SimpleNamespace(),
            SimpleNamespace(),
            create_repo_config(),
            repo_dir=str(repo_path),
        )
        clone_calls: list[object] = []
        monkeypatch.setattr(
            git_service,
            '_clone_repository',
            lambda progress_callback: clone_calls.append(progress_callback),
        )

        assert git_service._rebuild_repository(None) is False
        assert clone_calls == []
        assert (repo_path / '.git').is_dir()
        assert list(repo_path.glob('.git.corrupted.*')) == []

    def test_rebuild_repository_backs_up_git_directory_and_keeps_initial_tag(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        repo_path = tmp_path / 'repo'
        pygit2.init_repository(str(repo_path))
        git_service = GitService(
            SimpleNamespace(),
            SimpleNamespace(),
            create_repo_config(),
            repo_dir=str(repo_path),
        )

        received_tags: list[str | None] = []

        def fake_clone(
            progress_callback: object,
            initial_tag: str | None,
        ) -> tuple[GitSyncStatus, str]:
            received_tags.append(initial_tag)
            pygit2.init_repository(str(repo_path))
            return GitSyncStatus.SUCCESS, 'ok'

        monkeypatch.setattr(git_service, '_clone_repository', fake_clone)

        assert git_service._rebuild_repository(None, 'v1.0.0') is True
        assert received_tags == ['v1.0.0']
        assert (repo_path / '.git').is_dir()
        assert len(list(repo_path.glob('.git.corrupted.*'))) == 1

    def test_fetch_timeout_settings_are_configured_once(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(git_service_module, '_fetch_timeout_settings_configured', False)
        monkeypatch.setattr(git_service_module.settings, 'server_connect_timeout', 11)
        monkeypatch.setattr(git_service_module.settings, 'server_timeout', 22)

        with git_service._temporary_fetch_timeout():
            assert git_service_module.settings.server_connect_timeout == 30000
            assert git_service_module.settings.server_timeout == 30000

        assert git_service_module.settings.server_connect_timeout == 30000
        assert git_service_module.settings.server_timeout == 30000

        with git_service._temporary_fetch_timeout():
            assert git_service_module.settings.server_connect_timeout == 30000
            assert git_service_module.settings.server_timeout == 30000
