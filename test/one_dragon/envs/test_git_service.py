"""测试 GitService 的拉取进度回调。"""

from types import SimpleNamespace

import pytest

from one_dragon.envs.git_service import GitService, _FetchProgressRemoteCallbacks


class FakeRemote:

    def __init__(self, progress_stats: SimpleNamespace):
        self.name: str = 'origin'
        self.progress_stats: SimpleNamespace = progress_stats
        self.fetch_calls: list[dict[str, object]] = []

    def fetch(
        self,
        refspecs: list[str] | None = None,
        message: str | None = None,
        callbacks: object | None = None,
        prune: object | None = None,
        proxy: bool | str | None = None,
        depth: int = 0,
    ) -> SimpleNamespace:
        self.fetch_calls.append(
            {
                'refspecs': refspecs,
                'message': message,
                'callbacks': callbacks,
                'prune': prune,
                'proxy': proxy,
                'depth': depth,
            }
        )
        if callbacks is not None:
            callbacks.transfer_progress(self.progress_stats)
        return self.progress_stats


class TestFetchProgressRemoteCallbacks:
    """测试 _FetchProgressRemoteCallbacks 的当前行为。

    注意：当前实现中 stage 映射已上移到 GitService._create_fetch_callbacks，
    此处回调只接收 progress_callback，并直接传出原始进度（0.0~1.0）；
    消息格式包含百分比，例如「拉取对象 3/10 (30%)」。
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
            (1.0, '拉取对象 12/12 (100%)'),
        ]


class TestGitServiceFetchRemote:

    @pytest.fixture
    def git_service(self) -> GitService:
        project_config = SimpleNamespace(
            github_https_repository='https://example.com/repo.git',
            cnb_https_repository='https://example.com/repo.git',
            gitee_https_repository='https://example.com/repo.git',
        )
        env_config = SimpleNamespace(
            git_branch='main',
            git_remote='origin',
            is_personal_proxy=False,
            personal_proxy='',
        )
        return GitService(project_config, env_config, repo_dir='.')

    def test_fetch_remote_reports_progress_and_success(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = SimpleNamespace(references={})
        remote = FakeRemote(SimpleNamespace(received_objects=2, total_objects=4, received_bytes=2048))
        events: list[tuple[float, str]] = []

        monkeypatch.setattr(git_service, '_open_repo', lambda: repo)
        monkeypatch.setattr(git_service, '_ensure_remote', lambda: remote)

        result = git_service._fetch_remote(
            lambda progress, message: events.append((progress, message)),
            0.2,
            0.4,
        )

        assert result.success
        assert result.source_name == 'GitHub'
        assert remote.fetch_calls[0]['depth'] == 1
        assert remote.fetch_calls[0]['refspecs'] == ['+refs/heads/main:refs/remotes/origin/main']
        assert events[0] == (0.2, '从 GitHub 拉取代码')
        assert events[1][0] == pytest.approx(0.3)
        assert events[1][1] == '拉取对象 2/4 (50%)'
        assert events[-1] == (0.4, 'GitHub 拉取成功')
