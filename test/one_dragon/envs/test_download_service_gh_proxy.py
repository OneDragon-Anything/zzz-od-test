"""DownloadService 的 GitHub 代理线路回退。"""
from types import SimpleNamespace

import pytest

from one_dragon.envs.download_service import DownloadService
from one_dragon.envs.ghproxy_service import GhProxyService


class _FakeEnvConfig:
    """只带代理相关字段的 EnvConfig 替身。"""

    def __init__(self, is_gh_proxy: bool = True, is_personal_proxy: bool = False) -> None:
        self.gh_proxy_url: str = 'https://first.example'
        self.last_gh_proxy_url: str = ''
        self.personal_proxy: str = 'http://127.0.0.1:7890'
        self._is_gh_proxy: bool = is_gh_proxy
        self._is_personal_proxy: bool = is_personal_proxy

    @property
    def is_gh_proxy(self) -> bool:
        return self._is_gh_proxy

    @property
    def is_personal_proxy(self) -> bool:
        return self._is_personal_proxy


GITHUB_FILE_URL = 'https://github.com/OneDragon-Anything/OneDragon-Env/releases/download/v1/file.zip'


def _create_service(env_config: _FakeEnvConfig | None = None) -> tuple[DownloadService, _FakeEnvConfig]:
    env_config = env_config if env_config is not None else _FakeEnvConfig()
    repo_config = SimpleNamespace(gh_proxy_urls=('https://first.example', 'https://second.example'))
    gh_proxy_service = GhProxyService(env_config, repo_config)
    service = DownloadService(
        project_config=SimpleNamespace(project_name='ZenlessZoneZero-OneDragon'),
        env_config=env_config,
        repo_config=repo_config,
        gh_proxy_service=gh_proxy_service,
    )
    return service, env_config


class TestProxyFallback:

    def test_second_line_is_used_after_first_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, env_config = _create_service()
        attempted: list[str] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            attempted.append(url)
            return url.startswith('https://second.example')

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_file_from_url(GITHUB_FILE_URL, 'x.zip') is True
        assert attempted == [
            f'https://first.example/{GITHUB_FILE_URL}',
            f'https://second.example/{GITHUB_FILE_URL}',
        ]
        assert env_config.last_gh_proxy_url == 'https://second.example'
        assert env_config.gh_proxy_url == 'https://second.example'

    def test_all_lines_failed_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, env_config = _create_service()
        attempted: list[str] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            attempted.append(url)
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_file_from_url(GITHUB_FILE_URL, 'x.zip') is False
        assert len(attempted) == 2
        assert env_config.last_gh_proxy_url == ''

    def test_each_line_is_tried_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service()
        attempted: list[str] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            attempted.append(url)
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        service.download_file_from_url(GITHUB_FILE_URL, 'x.zip')
        assert attempted == [
            f'https://first.example/{GITHUB_FILE_URL}',
            f'https://second.example/{GITHUB_FILE_URL}',
        ]

    def test_non_github_url_is_downloaded_directly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service()
        attempted: list[str] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            attempted.append(url)
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_file_from_url('https://cnb.cool/a/b.zip', 'x.zip') is True
        assert attempted == ['https://cnb.cool/a/b.zip']

    def test_personal_proxy_is_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service(_FakeEnvConfig(is_gh_proxy=False, is_personal_proxy=True))
        received_proxy: list[str | None] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            received_proxy.append(proxy)
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_file_from_url(GITHUB_FILE_URL, 'x.zip') is True
        assert received_proxy == ['http://127.0.0.1:7890']
