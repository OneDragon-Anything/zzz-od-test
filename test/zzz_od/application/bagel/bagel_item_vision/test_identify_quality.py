from __future__ import annotations

import cv2
import numpy as np
import pytest

from zzz_od.application.bagel.bagel_item_vision import identify_quality


@pytest.mark.parametrize(('hue', 'quality'), [
    (0, 'Z'), (179, 'Z'), (23, 'S'), (50, 'C'), (73, 'C'), (85, 'C'),
    (90, 'B'), (109, 'B'), (110, 'B'), (119, 'B'),
    (120, 'A'), (139, 'A'), (160, 'A'),
    (14, '?'), (44, '?'), (87, '?'), (162, '?'),
])
def test_identify_quality_hue_bands(hue: int, quality: str) -> None:
    """蓝紫色带独立，未覆盖的色相不猜品质。"""
    hsv = np.full((8, 8, 3), (hue, 150, 180), dtype=np.uint8)
    assert identify_quality(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)) == quality


@pytest.mark.parametrize(('saturation', 'value'), [(0, 255), (39, 255), (150, 39)])
def test_identify_quality_rejects_gray_or_dark(saturation: int, value: int) -> None:
    """灰色或过暗背景仍为未知，不能直接兜底为 B、C。"""
    hsv = np.full((8, 8, 3), (73, saturation, value), dtype=np.uint8)
    assert identify_quality(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)) == '?'


def test_identify_quality_rejects_empty_or_grayscale() -> None:
    """无效裁剪不产生品质。"""
    assert identify_quality(np.empty((0, 0, 3), dtype=np.uint8)) == '?'
    assert identify_quality(np.full((8, 8), 180, dtype=np.uint8)) == '?'
