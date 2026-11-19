"""``OcrService`` 颜色过滤(color_range)回归测试, 不加载 OCR 模型。

覆盖 #2989 后续: None 透传原图; 合法 RGB/灰度范围生成三通道 255/0 掩码;
结构、通道数、非数字、下界高于上界均抛 ValueError, 且不会调用 OCR。
"""

import cv2
import numpy as np
import pytest
from cv2.typing import MatLike

from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.matcher.ocr.ocr_matcher import OcrMatcher
from one_dragon.base.matcher.ocr.ocr_service import OcrService


class RecordingOcrMatcher(OcrMatcher):
    """只记录入参图片的假 OCR 匹配器"""

    def __init__(self) -> None:
        super().__init__()
        self.received_images: list[MatLike] = []

    def ocr(self, image: MatLike, threshold: float = 0,
            merge_line_distance: float = -1) -> list[OcrMatchResult]:
        self.received_images.append(image)
        return []


@pytest.fixture
def ocr_service_and_matcher() -> tuple[OcrService, RecordingOcrMatcher]:
    matcher = RecordingOcrMatcher()
    return OcrService(matcher), matcher


# RGB 图: (0,0) 与 (1,1) 可命中, 其余像素不在范围内或超界
RGB_IMAGE = np.array(
    [
        [[10, 20, 30], [0, 0, 0]],
        [[255, 255, 255], [5, 15, 25]],
    ],
    dtype=np.uint8,
)
GRAY_IMAGE = np.array([[128, 10], [200, 100]], dtype=np.uint8)


@pytest.mark.parametrize(
    ('image', 'color_range', 'expected_mask'),
    [
        pytest.param(RGB_IMAGE, [[5, 15, 25], [15, 25, 35]],
                     [[255, 0], [0, 255]], id='rgb'),
        pytest.param(GRAY_IMAGE, [[100], [200]],
                     [[255, 0], [255, 255]], id='gray'),
        pytest.param(RGB_IMAGE, [[10, 20, 30], [10, 20, 30]],
                     [[255, 0], [0, 0]], id='equal-bounds'),
    ],
)
def test_color_range_mask(ocr_service_and_matcher, image, color_range, expected_mask) -> None:
    """合法范围: 命中像素为 255, 未命中为 0, 输出三通道"""
    service, matcher = ocr_service_and_matcher
    service.get_ocr_result_list(image, color_range=color_range)

    assert len(matcher.received_images) == 1
    processed = matcher.received_images[0]
    assert processed.shape == (image.shape[0], image.shape[1], 3)
    assert set(np.unique(processed).tolist()) <= {0, 255}
    expected = np.repeat(np.array(expected_mask, dtype=np.uint8)[:, :, None], 3, axis=2)
    assert np.array_equal(processed, expected)


def test_none_color_range_forwards_original_image(ocr_service_and_matcher) -> None:
    """color_range 为 None: 不复制、不改色, 原图对象直接交给 OCR"""
    service, matcher = ocr_service_and_matcher
    service.get_ocr_result_list(RGB_IMAGE, color_range=None)

    assert len(matcher.received_images) == 1
    assert matcher.received_images[0] is RGB_IMAGE


@pytest.mark.parametrize(
    ('image', 'color_range', 'message'),
    [
        pytest.param(RGB_IMAGE, [0, 0, 0], '颜色过滤配置格式有误', id='flat-three'),
        pytest.param(RGB_IMAGE, [0, 255], '颜色过滤配置格式有误', id='flat-two'),
        pytest.param(RGB_IMAGE, [[0], [255]], '通道数与图片不匹配', id='rgb-one-channel-bounds'),
        pytest.param(RGB_IMAGE, [[0, 0, 0, 0], [255, 255, 255, 255]],
                     '通道数与图片不匹配', id='rgb-four-channel-bounds'),
        pytest.param(GRAY_IMAGE, [[0, 0, 0], [255, 255, 255]],
                     '通道数与图片不匹配', id='gray-three-channel-bounds'),
    ],
)
def test_invalid_color_range_config_raises(ocr_service_and_matcher, image, color_range, message) -> None:
    """结构/通道数不合法: 抛 ValueError, 且不调用 OCR"""
    service, matcher = ocr_service_and_matcher
    with pytest.raises(ValueError, match=message):
        service.get_ocr_result_list(image, color_range=color_range)

    assert matcher.received_images == []


@pytest.mark.parametrize(
    ('image', 'color_range'),
    [
        pytest.param(RGB_IMAGE, [['a', 'b', 'c'], ['d', 'e', 'f']], id='rgb-strings'),
        pytest.param(GRAY_IMAGE, [['a'], ['b']], id='gray-strings'),
        pytest.param(RGB_IMAGE, [[None, 0, 0], [255, 255, 255]], id='rgb-none'),
    ],
)
def test_nonnumeric_color_range_raises_value_error_from_cv2(ocr_service_and_matcher, image, color_range) -> None:
    """非数字边界: cv2 报错被包装成 ValueError, 原始异常保留为 __cause__"""
    service, matcher = ocr_service_and_matcher
    with pytest.raises(ValueError, match='颜色过滤执行失败') as exc_info:
        service.get_ocr_result_list(image, color_range=color_range)

    assert isinstance(exc_info.value.__cause__, cv2.error)
    assert matcher.received_images == []


@pytest.mark.parametrize(
    ('image', 'color_range'),
    [
        pytest.param(GRAY_IMAGE, [[200], [100]], id='gray'),
        pytest.param(RGB_IMAGE, [[10, 0, 0], [5, 255, 255]], id='rgb-channel-0'),
        pytest.param(RGB_IMAGE, [[0, 10, 0], [255, 5, 255]], id='rgb-channel-1'),
        pytest.param(RGB_IMAGE, [[0, 0, 10], [255, 255, 5]], id='rgb-channel-2'),
    ],
)
def test_inverted_color_range_raises(ocr_service_and_matcher, image, color_range) -> None:
    """任一下界高于上界: 明确报出"下界不能高于上界", 且不调用 OCR"""
    service, matcher = ocr_service_and_matcher
    with pytest.raises(ValueError, match='下界不能高于上界'):
        service.get_ocr_result_list(image, color_range=color_range)

    assert matcher.received_images == []


def test_cached_color_range_is_revalidated_after_in_place_edit(
    ocr_service_and_matcher: tuple[OcrService, RecordingOcrMatcher],
) -> None:
    """同一图片上，普通缓存命中后，原地改坏配置仍应报错。"""
    service, matcher = ocr_service_and_matcher
    color_range = [[0, 0, 0], [100, 255, 255]]

    service.get_ocr_result_list(RGB_IMAGE, color_range=color_range)
    service.get_ocr_result_list(RGB_IMAGE, color_range=[[0, 0, 0], [100, 255, 255]])
    assert len(matcher.received_images) == 1

    color_range[0][0] = 200
    with pytest.raises(ValueError, match='下界不能高于上界'):
        service.get_ocr_result_list(RGB_IMAGE, color_range=color_range)
    assert len(matcher.received_images) == 1

    color_range[0][0] = 0
    service.get_ocr_result_list(RGB_IMAGE, color_range=color_range)
    assert len(matcher.received_images) == 1


def test_in_place_color_range_edit_recomputes_mask(
    ocr_service_and_matcher: tuple[OcrService, RecordingOcrMatcher],
) -> None:
    """原地改成另一个合法范围时，重新生成掩码并执行 OCR。"""
    service, matcher = ocr_service_and_matcher
    color_range = [[0], [255]]

    service.get_ocr_result_list(GRAY_IMAGE, color_range=color_range)
    color_range[0][0] = 100
    service.get_ocr_result_list(GRAY_IMAGE, color_range=color_range)

    assert len(matcher.received_images) == 2
    expected = np.array(
        [[[255, 255, 255], [0, 0, 0]], [[255, 255, 255], [255, 255, 255]]],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(matcher.received_images[1], expected)
