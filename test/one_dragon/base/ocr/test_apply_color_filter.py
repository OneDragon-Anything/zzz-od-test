import numpy as np
import pytest

from one_dragon.base.matcher.ocr.ocr_service import OcrService


@pytest.fixture
def service() -> OcrService:
    """只测颜色过滤纯函数 不加载 OCR 模型。"""
    return OcrService.__new__(OcrService)


@pytest.fixture
def image() -> np.ndarray:
    return np.zeros((10, 10, 3), dtype=np.uint8)


def test_normal_color_range(service: OcrService, image: np.ndarray) -> None:
    """正常配置过滤成功。"""
    out = service._apply_color_filter(image, [[0, 0, 0], [255, 255, 255]])
    assert out.shape == (10, 10, 3)


def test_none_color_range_returns_original(service: OcrService, image: np.ndarray) -> None:
    """None 直接返回原图 语义保持。"""
    assert service._apply_color_filter(image, None) is image


def test_malformed_color_range_raises_detailed_error(
        service: OcrService, image: np.ndarray) -> None:
    """配置缺上界时明确报出配置内容 而不是难懂的 IndexError。"""
    with pytest.raises(ValueError, match='格式有误'):
        service._apply_color_filter(image, [[0, 0, 0]])


def test_channel_mismatch_raises_detailed_error(
        service: OcrService, image: np.ndarray) -> None:
    """通道数不匹配时明确报出图片通道数与配置 而不是难懂的 cv2.error。"""
    with pytest.raises(ValueError, match='通道数'):
        service._apply_color_filter(image, [[0, 0, 0, 0], [255, 255, 255, 255]])


def test_in_range_failure_wrapped_with_context(
        service: OcrService, image: np.ndarray,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """inRange 执行失败时报错带配置上下文。"""

    def boom(*args, **kwargs):
        raise ValueError('mock inRange failure')

    monkeypatch.setattr('one_dragon.base.matcher.ocr.ocr_service.cv2.inRange', boom)

    with pytest.raises(ValueError, match='颜色过滤执行失败'):
        service._apply_color_filter(image, [[0, 0, 0], [255, 255, 255]])
