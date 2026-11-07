"""download_and_extract_env_file 的下载失败重试。"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.envs.download_service import DownloadService


class _FakeEnvConfig:
    """只带下载相关字段的 EnvConfig 替身。"""

    def __init__(self) -> None:
        self.env_source: str = 'https://github.com/OneDragon-Anything'
        self.last_env_source: str = ''
        self.personal_proxy: str = ''

    def get_env_source_candidates(self) -> list[str]:
        return [self.env_source]

    @property
    def is_gh_proxy(self) -> bool:
        return False

    @property
    def is_personal_proxy(self) -> bool:
        return False


def _create_service() -> DownloadService:
    """只带下载所需字段的 DownloadService，方便数重试次数。"""
    service = DownloadService.__new__(DownloadService)
    service.project_config = SimpleNamespace(project_name='ZenlessZoneZero-OneDragon')
    service.env_config = _FakeEnvConfig()
    service.gh_proxy_service = SimpleNamespace(
        get_candidate_urls=lambda: (),
        remember_success=lambda url: None,
        mark_failed=lambda url: None,
    )
    service._last_gh_proxy_url = None
    return service


class TestDownloadRetry:

    def test_download_failure_is_retried(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        service = _create_service()
        attempts: list[int] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            attempts.append(1)
            if len(attempts) == 1:
                return False
            Path(save_file_path).write_bytes(b'zip')
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)
        def fake_unzip(zip_path: str, extract_dir: str) -> bool:
            Path(extract_dir).mkdir(parents=True, exist_ok=True)
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', fake_unzip)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is True
        assert len(attempts) == 2

    def test_download_failure_uses_all_attempts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        service = _create_service()
        attempts: list[int] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            attempts.append(1)
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_and_extract_env_file(
            'env.zip', str(tmp_path), str(tmp_path / 'out'), retry_count=3,
        ) is False
        assert len(attempts) == 3

    def test_existing_broken_zip_is_redownloaded(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        service = _create_service()
        downloads: list[str] = []
        unzip_calls: list[int] = []

        (tmp_path / 'env.zip').write_bytes(b'zip')

        monkeypatch.setattr(
            'one_dragon.envs.download_service.http_utils.download_file',
            lambda url, save_file_path, proxy=None, progress_callback=None: downloads.append(url) or True,
        )

        def fake_unzip(zip_path: str, extract_dir: str) -> bool:
            unzip_calls.append(1)
            if len(unzip_calls) > 1:
                Path(extract_dir).mkdir(parents=True, exist_ok=True)
                return True
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', fake_unzip)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is True
        # 第一次用的是已存在的旧包 解压失败后删掉重下
        assert downloads == ['https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/env.zip']
        assert len(unzip_calls) == 2
