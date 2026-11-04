"""测试 DownloadService 的环境文件下载多源回退。"""

from types import SimpleNamespace

import pytest

from one_dragon.envs.download_service import DownloadService
from one_dragon.envs.repo_config import SourceOption

SOURCE_OPTIONS = (
    SourceOption('github', 'GitHub', 'https://github.example/OneDragon-Env/releases/download'),
    SourceOption('cnb', 'CNB', 'https://cnb.example/OneDragon-Env/releases/download'),
    SourceOption('gitee', 'Gitee', 'https://gitee.example/OneDragon-Env/releases/download'),
)

ENV_SOURCE_CNB = 'https://cnb.example/OneDragon-Env/releases/download'


@pytest.fixture
def download_service() -> DownloadService:
    project_config = SimpleNamespace(project_name='ZenlessZoneZero-OneDragon')
    repo_config = SimpleNamespace(
        get_source_values=lambda source_name: SOURCE_OPTIONS if source_name == 'env_source' else (),
    )
    env_config = SimpleNamespace(env_source=ENV_SOURCE_CNB, repo_config=repo_config)
    return DownloadService(project_config, env_config)


def test_candidates_prioritize_current_source(download_service: DownloadService) -> None:
    assert download_service._get_env_source_candidates() == [
        'https://cnb.example/OneDragon-Env/releases/download',
        'https://github.example/OneDragon-Env/releases/download',
        'https://gitee.example/OneDragon-Env/releases/download',
    ]


def test_candidates_deduplicate_current_builtin_source(download_service: DownloadService) -> None:
    download_service.env_config.env_source = 'https://github.example/OneDragon-Env/releases/download'

    assert download_service._get_env_source_candidates() == [
        'https://github.example/OneDragon-Env/releases/download',
        'https://cnb.example/OneDragon-Env/releases/download',
        'https://gitee.example/OneDragon-Env/releases/download',
    ]


def test_candidates_ignore_blank_current_source(download_service: DownloadService) -> None:
    download_service.env_config.env_source = '   '

    assert download_service._get_env_source_candidates() == [
        'https://github.example/OneDragon-Env/releases/download',
        'https://cnb.example/OneDragon-Env/releases/download',
        'https://gitee.example/OneDragon-Env/releases/download',
    ]


def test_download_env_file_uses_first_success(
    download_service: DownloadService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_urls: list[str] = []
    monkeypatch.setattr(
        download_service,
        'download_file_from_url',
        lambda download_url, save_file_path, progress_callback: (
            attempted_urls.append(download_url) or True
        ),
    )

    assert download_service.download_env_file('cpython-3.11.zip', 'save.zip') is True
    assert attempted_urls == [
        f'{ENV_SOURCE_CNB}/ZenlessZoneZero-OneDragon/cpython-3.11.zip',
    ]
    assert download_service.env_config.env_source == ENV_SOURCE_CNB


def test_download_env_file_falls_back_and_persists_success_source(
    download_service: DownloadService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_urls: list[str] = []
    github_source = SOURCE_OPTIONS[0].value

    def fake_download(download_url: str, save_file_path: str, progress_callback: object) -> bool:
        attempted_urls.append(download_url)
        return github_source in download_url

    monkeypatch.setattr(download_service, 'download_file_from_url', fake_download)

    assert download_service.download_env_file('cpython-3.11.zip', 'save.zip') is True
    assert attempted_urls == [
        f'{ENV_SOURCE_CNB}/ZenlessZoneZero-OneDragon/cpython-3.11.zip',
        f'{github_source}/ZenlessZoneZero-OneDragon/cpython-3.11.zip',
    ]
    assert download_service.env_config.env_source == github_source


def test_download_env_file_all_sources_failed(
    download_service: DownloadService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_urls: list[str] = []
    monkeypatch.setattr(
        download_service,
        'download_file_from_url',
        lambda download_url, save_file_path, progress_callback: (
            attempted_urls.append(download_url) or False
        ),
    )

    assert download_service.download_env_file('cpython-3.11.zip', 'save.zip') is False
    assert len(attempted_urls) == 3
    assert download_service.env_config.env_source == ENV_SOURCE_CNB
