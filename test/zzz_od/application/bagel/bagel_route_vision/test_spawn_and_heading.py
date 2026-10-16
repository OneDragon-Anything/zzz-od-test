from __future__ import annotations

import pytest
from test.zzz_od.application.bagel.bagel_route_vision.conftest import (
    archived_state,
)

from one_dragon.utils import cal_utils
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision


@pytest.mark.parametrize(
    'state,expected',
    [
        ('雅努斯出生-r01-39s.webp', 0),
        ('雅努斯转角定位失败-1440缩放.webp', 260),
    ],
)
def test_archived_arrow(vision: BagelRouteVision, state: str, expected: float) -> None:
    """独立截图尖端朝向与人工核对方向一致，容纳低分辨率边缘误差。"""
    angle = vision.player_angle(archived_state(state))
    assert angle is not None
    assert abs(cal_utils.angle_delta(angle, expected)) < 7
