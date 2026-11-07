"""OCR 模型懒加载时的 GitHub 代理线路服务。"""

import threading
from types import SimpleNamespace

from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher


class _FakeEnvConfig:

    def __init__(self, is_gh_proxy: bool) -> None:
        self.is_gh_proxy: bool = is_gh_proxy


def _create_matcher(
        monkeypatch,
        cached_service: SimpleNamespace | None,
) -> tuple[OnnxOcrMatcher, list[SimpleNamespace | None]]:
    matcher = object.__new__(OnnxOcrMatcher)
    matcher._init_lock = threading.Lock()
    matcher._model = None
    # 用真实方法补齐下载设置字段，再放回要验证的缓存服务
    OnnxOcrMatcher.set_download_options(matcher)
    matcher._gh_proxy_service = cached_service
    received: list[SimpleNamespace | None] = []
    calls: list[dict] = []
    matcher.download_calls = calls

    def fake_download(**kwargs) -> bool:
        calls.append(kwargs)
        received.append(kwargs.get('gh_proxy_service'))
        return False

    monkeypatch.setattr(matcher, 'download', fake_download)
    return matcher, received


def test_cached_proxy_service_dropped_after_switching_to_direct(monkeypatch) -> None:
    """用户改成直连后 懒加载不能再用缓存里的线路服务。"""
    service = SimpleNamespace(env_config=_FakeEnvConfig(is_gh_proxy=False))
    matcher, received = _create_matcher(monkeypatch, service)

    assert matcher.init_model() is False
    assert matcher._gh_proxy_service is None
    assert received == [None]


def test_explicit_service_is_kept(monkeypatch) -> None:
    service = SimpleNamespace(env_config=_FakeEnvConfig(is_gh_proxy=True))
    matcher, received = _create_matcher(monkeypatch, None)

    assert matcher.init_model(gh_proxy_service=service) is False
    assert matcher._gh_proxy_service is service
    assert received == [service]

def test_lazy_init_reuses_saved_download_options(monkeypatch) -> None:
    """用户取消下载后 OCR 懒加载 仍要用初始化时记下的源与代理设置。"""
    service = SimpleNamespace(env_config=_FakeEnvConfig(is_gh_proxy=True))
    matcher, received = _create_matcher(monkeypatch, None)
    matcher.set_download_options(
        source_order=['github', 'cnb'],
        proxy_url='http://127.0.0.1:7890',
        ghproxy_url='https://gh-proxy.com',
        gh_proxy_service=service,
        on_source_success=None,
        on_source_failure=None,
        fallback_on_slow=True,
    )

    assert matcher.init_model() is False
    assert received == [service]
    assert matcher.download_calls[0]['source_order'] == ['github', 'cnb']
    assert matcher.download_calls[0]['proxy_url'] == 'http://127.0.0.1:7890'
    assert matcher.download_calls[0]['ghproxy_url'] == 'https://gh-proxy.com'
    assert matcher.download_calls[0]['fallback_on_slow'] is True
