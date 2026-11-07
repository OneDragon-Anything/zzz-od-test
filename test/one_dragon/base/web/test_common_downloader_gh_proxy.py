"""CommonDownloader 对 GitHub 源逐条尝试 ghproxy 候选线路。"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.web.common_downloader import (
    CommonDownloader,
    CommonDownloaderParam,
)
from one_dragon.envs.ghproxy_service import GhProxyService

GITHUB_URL = 'https://github.com/OneDragon-Anything/OneDragon-YOLO/releases/download/tag/model.zip'
CNB_URL = 'https://cnb.cool/OneDragon-Anything/OneDragon-YOLO/-/releases/download/tag/model.zip'


class _FakeEnvConfig:
    """只带代理相关字段的 EnvConfig 替身。"""

    def __init__(self) -> None:
        self.gh_proxy_url: str = 'https://first.example'
        self.last_gh_proxy_url: str = ''


def _create_downloader(
    download_urls: dict[str, str] | None = None,
) -> tuple[CommonDownloader, GhProxyService]:
    param = CommonDownloaderParam(
        save_file_path='.',
        save_file_name='model.zip',
        download_urls={
            'github': GITHUB_URL,
            'cnb': CNB_URL,
        }
        if download_urls is None
        else download_urls,
    )
    env_config = _FakeEnvConfig()
    repo_config = SimpleNamespace(gh_proxy_urls=('https://first.example', 'https://second.example'))
    service = GhProxyService(env_config, repo_config)
    return CommonDownloader(param), service


class TestGithubSourceProxyFallback:

    def test_second_line_used_after_first_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        downloader, service = _create_downloader()
        attempted: list[str] = []
        succeeded_sources: list[str] = []

        def fake_download(download_url: str, **kwargs) -> bool:
            attempted.append(download_url)
            return download_url.startswith('https://second.example')

        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)

        assert downloader.download(
            source_order=['github'],
            gh_proxy_service=service,
            on_source_success=succeeded_sources.append,
        ) is True
        assert attempted == [
            f'https://first.example/{GITHUB_URL}',
            f'https://second.example/{GITHUB_URL}',
        ]
        assert succeeded_sources == ['github']
        assert service.env_config.last_gh_proxy_url == 'https://second.example'

    def test_source_failure_reported_once_after_all_lines(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        downloader, service = _create_downloader()
        failed_sources: list[str] = []

        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.http_utils.download_file',
            lambda download_url, **kwargs: False,
        )

        assert downloader.download(
            source_order=['github'],
            gh_proxy_service=service,
            on_source_failure=failed_sources.append,
        ) is False
        assert failed_sources == ['github']

    def test_next_source_used_after_all_lines_fail(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        downloader, service = _create_downloader()
        attempted: list[str] = []

        def fake_download(download_url: str, **kwargs) -> bool:
            attempted.append(download_url)
            return download_url == CNB_URL

        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)

        assert downloader.download(
            source_order=['github', 'cnb'],
            gh_proxy_service=service,
        ) is True
        assert attempted == [
            f'https://first.example/{GITHUB_URL}',
            f'https://second.example/{GITHUB_URL}',
            CNB_URL,
        ]

    def test_non_github_source_has_no_proxy_prefix(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        downloader, service = _create_downloader()
        attempted: list[str] = []

        def fake_download(download_url: str, **kwargs) -> bool:
            attempted.append(download_url)
            return True

        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)

        assert downloader.download(source_order=['cnb'], gh_proxy_service=service) is True
        assert attempted == [CNB_URL]

    def test_cancel_stops_remaining_lines(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        downloader, service = _create_downloader()
        attempted: list[str] = []
        progress_signal: dict[str, str | None] = {'signal': None}

        def fake_download(download_url: str, **kwargs) -> bool:
            attempted.append(download_url)
            progress_signal['signal'] = 'cancel'
            return False

        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)

        assert downloader.download(
            source_order=['github', 'cnb'],
            gh_proxy_service=service,
            progress_signal=progress_signal,
        ) is False
        assert tried_single_line(attempted)

    def test_single_ghproxy_url_still_supported(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        downloader, _ = _create_downloader()
        attempted: list[str] = []

        def fake_download(download_url: str, **kwargs) -> bool:
            attempted.append(download_url)
            return True

        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)

        assert downloader.download(
            source_order=['github'],
            ghproxy_url='https://legacy.example/',
        ) is True
        assert attempted == [f'https://legacy.example/{GITHUB_URL}']


def tried_single_line(attempted: list[str]) -> bool:
    """取消后只应该尝试第一条线路。"""
    return attempted == [f'https://first.example/{GITHUB_URL}']

class TestZipRetryAfterBrokenContent:

    def test_broken_zip_retry_uses_next_line(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from one_dragon.base.web.zip_downloader import ZipDownloader

        env_config = _FakeEnvConfig()
        repo_config = SimpleNamespace(gh_proxy_urls=('https://first.example', 'https://second.example'))
        service = GhProxyService(env_config, repo_config)
        param = CommonDownloaderParam(
            save_file_path='.',
            save_file_name='model.zip',
            download_urls={'github': GITHUB_URL},
            check_existed_list=['model.onnx'],
        )
        downloader = ZipDownloader(param)
        attempted: list[str] = []

        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.http_utils.download_file',
            lambda download_url, **kwargs: attempted.append(download_url) or True,
        )
        monkeypatch.setattr(downloader, 'unzip', lambda: len(attempted) > 1)
        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.CommonDownloader.is_file_existed',
            lambda _self: len(attempted) > 1,
        )

        assert downloader.download(
            source_order=['github'],
            gh_proxy_service=service,
        ) is True
        assert attempted == [
            f'https://first.example/{GITHUB_URL}',
            f'https://second.example/{GITHUB_URL}',
        ]


    def test_line_recorded_only_after_unzip_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from one_dragon.base.web.zip_downloader import ZipDownloader

        env_config = _FakeEnvConfig()
        repo_config = SimpleNamespace(gh_proxy_urls=('https://first.example', 'https://second.example'))
        service = GhProxyService(env_config, repo_config)
        param = CommonDownloaderParam(
            save_file_path='.',
            save_file_name='model.zip',
            download_urls={'github': GITHUB_URL},
            check_existed_list=['model.onnx'],
        )
        downloader = ZipDownloader(param)
        unzip_results: list[bool] = []

        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.http_utils.download_file',
            lambda download_url, **kwargs: True,
        )

        def fake_unzip() -> bool:
            return unzip_results.pop(0)

        monkeypatch.setattr(downloader, 'unzip', fake_unzip)
        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.CommonDownloader.is_file_existed',
            lambda _self: bool(unzip_results) is False,
        )

        unzip_results.extend([False, True])
        assert downloader.download(source_order=['github'], gh_proxy_service=service) is True
        assert env_config.last_gh_proxy_url == 'https://second.example', '坏包那条线路不能被记成首选'

    def test_source_success_callback_waits_for_unzip(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from one_dragon.base.web.zip_downloader import ZipDownloader

        env_config = _FakeEnvConfig()
        repo_config = SimpleNamespace(gh_proxy_urls=('https://first.example', 'https://second.example'))
        service = GhProxyService(env_config, repo_config)
        param = CommonDownloaderParam(
            save_file_path='.',
            save_file_name='model.zip',
            download_urls={'github': GITHUB_URL},
            check_existed_list=['model.onnx'],
        )
        downloader = ZipDownloader(param)
        events: list[tuple[str, str]] = []
        unzip_results: list[bool] = []

        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.http_utils.download_file',
            lambda download_url, **kwargs: True,
        )
        monkeypatch.setattr(downloader, 'unzip', lambda: unzip_results.pop(0))
        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.CommonDownloader.is_file_existed',
            lambda _self: not unzip_results,
        )

        unzip_results.extend([False, True])
        assert downloader.download(
            source_order=['github'],
            gh_proxy_service=service,
            on_source_success=lambda source_id: events.append(('success', source_id)),
            on_source_failure=lambda source_id: events.append(('failure', source_id)),
        ) is True
        # 第一次压缩包坏了要回调失败 第二次解压成功才回调成功
        assert events == [('failure', 'github'), ('success', 'github')]

    def test_last_source_id_cleared_on_each_download(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """再次调用时文件已存在 不能拿上一次的源 ID 回调成功。"""
        from one_dragon.base.web.zip_downloader import ZipDownloader

        target = tmp_path / 'model.onnx'
        param = CommonDownloaderParam(
            save_file_path=str(tmp_path),
            save_file_name='model.zip',
            download_urls={'github': GITHUB_URL},
            check_existed_list=[str(target)],
        )
        downloader = ZipDownloader(param)
        events: list[str] = []

        def fake_download(download_url: str, **kwargs) -> bool:
            target.write_bytes(b'model')
            return True

        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)
        monkeypatch.setattr(downloader, 'unzip', lambda: True)

        assert downloader.download(
            source_order=['github'],
            on_source_success=events.append,
        ) is True
        assert events == ['github']

        # 第二次：文件已存在 基类直接返回 不应再拿上次的源 ID 回调
        assert downloader.download(source_order=['github'], on_source_success=events.append) is True
        assert events == ['github']

    def test_unzip_failure_from_file_utils_cleans_partial_output(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """unzip_file 返回失败时不能因为残留文件存在就判成解压成功。"""
        from one_dragon.base.web.zip_downloader import ZipDownloader

        target = tmp_path / 'model.onnx'
        param = CommonDownloaderParam(
            save_file_path=str(tmp_path),
            save_file_name='model.zip',
            download_urls={'github': GITHUB_URL},
            check_existed_list=[str(target)],
        )
        downloader = ZipDownloader(param)
        (tmp_path / 'model.zip').write_bytes(b'zip')

        def fake_unzip(**kwargs) -> bool:
            # 模拟解压中途失败 只写出了一个半成品
            target.write_bytes(b'partial')
            return False

        monkeypatch.setattr('one_dragon.base.web.zip_downloader.file_utils.unzip_file', fake_unzip)

        assert downloader.unzip() is False
        assert not target.exists(), '解压失败要清掉写了一半的产物'

    def test_broken_zip_switches_to_next_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """首选源给坏包时 本次调用要换到下一个源 而不是一直重试首选源。"""
        from one_dragon.base.web.zip_downloader import ZipDownloader

        cnb_url = 'https://cnb.cool/OneDragon-Anything/OneDragon-Env/-/releases/download/m/x.zip'
        param = CommonDownloaderParam(
            save_file_path='.',
            save_file_name='model.zip',
            download_urls={'cnb': cnb_url, 'github': GITHUB_URL},
            check_existed_list=['model.onnx'],
        )
        downloader = ZipDownloader(param)
        requested: list[str] = []

        def fake_download(download_url: str, **kwargs) -> bool:
            requested.append(download_url)
            return True

        unzip_results: list[bool] = [False, True]
        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)
        monkeypatch.setattr(downloader, 'unzip', lambda: unzip_results.pop(0))
        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.CommonDownloader.is_file_existed',
            lambda _self: not unzip_results,
        )

        assert downloader.download(source_order=['cnb', 'github']) is True
        assert requested == [cnb_url, GITHUB_URL], '坏包源本轮不再重试 直接换下一个源'

    def test_github_bad_line_keeps_source_for_next_line(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """github 还有线路没试时 坏包只换线路 不排除整个 github 源。"""
        from one_dragon.base.web.zip_downloader import ZipDownloader

        env_config = _FakeEnvConfig()
        repo_config = SimpleNamespace(gh_proxy_urls=('https://first.example', 'https://second.example'))
        service = GhProxyService(env_config, repo_config)
        param = CommonDownloaderParam(
            save_file_path='.',
            save_file_name='model.zip',
            download_urls={'github': GITHUB_URL},
            check_existed_list=['model.onnx'],
        )
        downloader = ZipDownloader(param)
        requested: list[str] = []

        def fake_download(download_url: str, **kwargs) -> bool:
            requested.append(download_url)
            return True

        unzip_results: list[bool] = [False, True]
        monkeypatch.setattr('one_dragon.base.web.common_downloader.http_utils.download_file', fake_download)
        monkeypatch.setattr(downloader, 'unzip', lambda: unzip_results.pop(0))
        monkeypatch.setattr(
            'one_dragon.base.web.common_downloader.CommonDownloader.is_file_existed',
            lambda _self: not unzip_results,
        )

        assert downloader.download(source_order=['github'], gh_proxy_service=service) is True
        assert requested == [
            f'https://first.example/{GITHUB_URL}',
            f'https://second.example/{GITHUB_URL}',
        ]
