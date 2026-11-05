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
    matcher._gh_proxy_service = cached_service
    received: list[SimpleNamespace | None] = []
    monkeypatch.setattr(matcher, 'download', lambda **kwargs: received.append(kwargs.get('gh_proxy_service')) or False)
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
