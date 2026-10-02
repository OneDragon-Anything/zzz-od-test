"""使用已归档箭头和旋转样本验证角色方向，不把扇区当成箭头。"""

import cv2
import numpy as np
import pytest
from test.zzz_od.application.bagel.bagel_route_vision.conftest import archived_state

from one_dragon.utils import cal_utils
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision


@pytest.mark.parametrize('state,expected', [
    ('雅努斯出生-r01-39s.webp', 0),
    ('雅努斯出生-r07-30s.webp', 0),
    ('雅努斯箱前-r07-32s.webp', 250),
    ('雅努斯转角定位失败-1440缩放.webp', 260),
])
def test_archived_arrow(vision: BagelRouteVision, state: str, expected: float) -> None:
    """独立截图尖端朝向与人工核对方向一致，容纳低分辨率边缘误差。"""
    angle = vision.player_angle(archived_state(state))
    assert angle is not None
    assert abs(cal_utils.angle_delta(angle, expected)) < 7


@pytest.mark.parametrize('angle', [0, 45, 90, 135, 180, 225, 270, 315])
def test_rotated_arrow(vision: BagelRouteVision, angle: float) -> None:
    """旋转真实箭头检查象限和正负号，覆盖越过零度。"""
    crop = archived_state('雅努斯出生-r01-39s.webp')
    transform = cv2.getRotationMatrix2D((100, 100), -angle, 1)
    rotated = cv2.warpAffine(crop, transform, (201, 201))
    actual = vision.player_angle(rotated)
    assert actual is not None
    assert abs(cal_utils.angle_delta(actual, angle)) < 7


@pytest.mark.parametrize('kind', ['blank', 'uniform', 'missing_arrow', 'wrong_shape'])
def test_unreadable_arrow_stops(vision: BagelRouteVision, kind: str) -> None:
    """空画面、纯色黄色块或只有扇区时不能凭背景猜朝向。"""
    crop = np.zeros((201, 201, 3), np.uint8)
    if kind == 'uniform':
        cv2.circle(crop, (100, 100), 10, (0, 200, 255), -1)
    elif kind == 'missing_arrow':
        crop = archived_state('雅努斯出生-r01-39s.webp')
        crop[80:121, 80:121] = 0
    elif kind == 'wrong_shape':
        crop = crop[:100]
    assert vision.player_angle(crop) is None
