"""DownloadService 的 GitHub 代理线路回退。"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.envs.download_service import DownloadService
from one_dragon.envs.ghproxy_service import GhProxyService


class _FakeEnvConfig:
    """只带代理相关字段的 EnvConfig 替身。"""

    def __init__(self, is_gh_proxy: bool = True, is_personal_proxy: bool = False) -> None:
        self.env_source: str = 'https://github.com/OneDragon-Anything'
        self.gh_proxy_url: str = 'https://first.example'
        self.last_gh_proxy_url: str = ''
        self.personal_proxy: str = 'http://127.0.0.1:7890'
        self._is_gh_proxy: bool = is_gh_proxy
        self._is_personal_proxy: bool = is_personal_proxy
        self.last_env_source: str = ''

    @property
    def is_gh_proxy(self) -> bool:
        return self._is_gh_proxy

    def get_env_source_candidates(self) -> list[str]:
        return [self.env_source]

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

    def test_broken_content_switches_line_on_retry(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        service, _ = _create_service()
        attempted: list[str] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None) -> bool:
            attempted.append(url)
            Path(save_file_path).write_bytes(b'not a zip')
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)
        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', lambda *args: False)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is False
        env_url = 'https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/env.zip'
        assert attempted == [
            f'https://first.example/{env_url}',
            f'https://second.example/{env_url}',
        ]

    def test_broken_lines_then_next_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """一个源的两条线路都返回坏包时，换下一个源，成功的源和线路都要记录下来。"""
        env_config = _FakeEnvConfig()
        env_config.env_source = 'https://github.com/OneDragon-Anything'
        env_config.last_env_source = ''
        env_config._sources = [
            'https://github.com/OneDragon-Anything',
            'https://cnb.cool/OneDragon-Anything',
        ]
        env_config.get_env_source_candidates = lambda: list(env_config._sources)  # type: ignore[method-assign]
        repo_config = SimpleNamespace(gh_proxy_urls=('https://first.example', 'https://second.example'))
        service = DownloadService(
            project_config=SimpleNamespace(project_name='ZenlessZoneZero-OneDragon'),
            env_config=env_config,
            repo_config=repo_config,
            gh_proxy_service=GhProxyService(env_config, repo_config),
        )
        attempted: list[str] = []
        unzip_results: list[bool] = []

        def fake_download(
                url: str,
                save_file_path: str,
                proxy=None,
                progress_callback=None,
                **kwargs,
        ) -> bool:
            attempted.append(url)
            Path(save_file_path).write_bytes(b'zip')
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)
        def fake_unzip(zip_path: str, extract_dir: str) -> bool:
            if unzip_results.pop(0):
                Path(extract_dir).mkdir(parents=True, exist_ok=True)
                return True
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', fake_unzip)

        # 第一条源的两条线路都坏，第二个源下载成功
        unzip_results.extend([False, False, True])
        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is True

        github_url = 'https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/env.zip'
        cnb_url = 'https://cnb.cool/OneDragon-Anything/ZenlessZoneZero-OneDragon/env.zip'
        assert attempted == [
            f'https://first.example/{github_url}',
            f'https://second.example/{github_url}',
            cnb_url,
        ], 'cnb 源不是 github 地址 直接下载 不拼代理前缀'
        assert env_config.last_env_source == 'https://cnb.cool/OneDragon-Anything'
        assert env_config.last_gh_proxy_url == 'https://second.example'


class TestSourceAwareRetry:

    def _service_with_sources(
        self,
        sources: list[str],
        lines: tuple[str, ...] = ('https://first.example', 'https://second.example'),
    ) -> tuple[DownloadService, _FakeEnvConfig, GhProxyService]:
        env_config = _FakeEnvConfig()
        env_config.env_source = sources[0]
        env_config.last_env_source = ''
        env_config.get_env_source_candidates = lambda: list(sources)  # type: ignore[method-assign]
        repo_config = SimpleNamespace(gh_proxy_urls=lines)
        gh_proxy_service = GhProxyService(env_config, repo_config)
        service = DownloadService(
            project_config=SimpleNamespace(project_name='ZenlessZoneZero-OneDragon'),
            env_config=env_config,
            repo_config=repo_config,
            gh_proxy_service=gh_proxy_service,
        )
        return service, env_config, gh_proxy_service

    def test_non_github_source_keeps_retry_count(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """线路数只影响 github 源 CNB 等源仍按 retry_count 重试。"""
        service, _, _ = self._service_with_sources(['https://cnb.cool/OneDragon-Anything'])
        attempted: list[str] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            attempted.append(url)
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is False
        assert len(attempted) == 2, '非 github 源不该按线路数放大重试次数'

    def test_failed_lines_are_not_requested_again(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """下载失败的线路记入排除集合 同源重试不再重复请求。"""
        service, _, _ = self._service_with_sources(['https://github.com/OneDragon-Anything'])
        attempted: list[str] = []

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            attempted.append(url)
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is False
        assert len(attempted) == 2, '两条线路各请求一次 重试时不再重复'
        assert attempted[0] != attempted[1]

    def test_existing_zip_does_not_record_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """已有压缩包直接解压成功时 没下载过就不能记成上次成功源。"""
        service, env_config, _ = self._service_with_sources(['https://github.com/OneDragon-Anything'])
        (tmp_path / 'env.zip').write_bytes(b'zip')

        def fail_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            raise AssertionError('已有压缩包不应该再下载')

        def fake_unzip(zip_path: str, extract_dir: str) -> bool:
            Path(extract_dir).mkdir(parents=True, exist_ok=True)
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fail_download)
        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', fake_unzip)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is True
        assert env_config.last_env_source == ''

    def test_extract_failure_keeps_existing_install(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """所有源都失败时不能把 existing 环境目录删掉。"""
        service, _, _ = self._service_with_sources(['https://github.com/OneDragon-Anything'])
        out = tmp_path / 'out'
        out.mkdir()
        (out / 'keep.txt').write_text('keep', encoding='utf-8')

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            Path(save_file_path).write_bytes(b'bad')
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)
        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', lambda *args: False)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(out)) is False
        assert (out / 'keep.txt').exists(), '解压失败的临时目录不能替换现有环境'
        assert not (tmp_path / 'out_extract_tmp').exists(), '临时目录要清理干净'

    def test_replace_failure_restores_previous_install(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """临时目录换成目标目录失败时 现有环境要还原。"""
        service, _, _ = self._service_with_sources(['https://github.com/OneDragon-Anything'])
        out = tmp_path / 'out'
        out.mkdir()
        (out / 'keep.txt').write_text('keep', encoding='utf-8')

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            Path(save_file_path).write_bytes(b'zip')
            return True

        def fake_unzip(zip_path: str, extract_dir: str) -> bool:
            Path(extract_dir).mkdir(parents=True, exist_ok=True)
            (Path(extract_dir) / 'new.txt').write_text('new', encoding='utf-8')
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)
        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', fake_unzip)

        original_rename = Path.rename
        calls: list[int] = []

        def failing_rename(self_path: Path, target) -> None:
            calls.append(1)
            if len(calls) == 2:
                raise OSError('目录被占用')
            original_rename(self_path, target)

        monkeypatch.setattr(Path, 'rename', failing_rename)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(out)) is False
        assert (out / 'keep.txt').exists(), '替换失败要把原来的目录还回去'
        assert not (out / 'new.txt').exists()

    def test_leftover_backup_is_restored_before_replace(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """上次恢复失败留下的备份 要先还原再替换 不能直接删。"""
        service, _, _ = self._service_with_sources(['https://github.com/OneDragon-Anything'])
        backup = tmp_path / 'out_bak_tmp'
        backup.mkdir()
        (backup / 'old.txt').write_text('old', encoding='utf-8')

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            Path(save_file_path).write_bytes(b'zip')
            return True

        def fake_unzip(zip_path: str, extract_dir: str) -> bool:
            Path(extract_dir).mkdir(parents=True, exist_ok=True)
            (Path(extract_dir) / 'new.txt').write_text('new', encoding='utf-8')
            return True

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)
        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', fake_unzip)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is True
        assert (tmp_path / 'out' / 'new.txt').exists()
        assert not backup.exists(), '替换成功后备份可以删掉'

    def test_backup_cleanup_failure_keeps_install_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """新目录已换好时 备份删不掉只记日志 不能把安装判成失败。"""
        service, _, _ = self._service_with_sources(['https://github.com/OneDragon-Anything'])
        out = tmp_path / 'out'
        out.mkdir()

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            Path(save_file_path).write_bytes(b'zip')
            return True

        def fake_unzip(zip_path: str, extract_dir: str) -> bool:
            Path(extract_dir).mkdir(parents=True, exist_ok=True)
            return True

        import shutil as _shutil

        real_rmtree = _shutil.rmtree

        def failing_rmtree(path, *args, **kwargs) -> None:
            if str(path).endswith('_bak_tmp'):
                raise OSError('备份目录被占用')
            real_rmtree(path, *args, **kwargs)

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)
        monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file', fake_unzip)
        monkeypatch.setattr('one_dragon.envs.download_service.shutil.rmtree', failing_rmtree)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(out)) is True

    def test_leftover_backup_restored_even_if_all_sources_fail(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """上次替换中断留下备份时 这次即使全部失败也要先把环境还原回来。"""
        service, _, _ = self._service_with_sources(['https://github.com/OneDragon-Anything'])
        backup = tmp_path / 'out_bak_tmp'
        backup.mkdir()
        (backup / 'old.txt').write_text('old', encoding='utf-8')

        def fake_download(url: str, save_file_path: str, proxy=None, progress_callback=None, **kwargs) -> bool:
            return False

        monkeypatch.setattr('one_dragon.envs.download_service.http_utils.download_file', fake_download)

        assert service.download_and_extract_env_file('env.zip', str(tmp_path), str(tmp_path / 'out')) is False
        assert (tmp_path / 'out' / 'old.txt').exists(), '旧环境要先还原回来'
