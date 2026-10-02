"""两张小地图参考图的统一坐标。"""

import numpy as np
import pytest
from test.zzz_od.application.bagel.bagel_route_vision.conftest import (
    archived_crop,
    archived_state,
)

from zzz_od.application.bagel.bagel_minimap import MinimapMatch
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision


@pytest.mark.parametrize('round_number,second,expected', [
    (1, 39, (100, 100)),
    (7, 30, (99, 100)),
])
def test_spawn_cross_round(
    vision: BagelRouteVision, round_number: int, second: int, expected: tuple[int, int],
) -> None:
    """出生位置在独立局仍能投影到第一局参考图。"""
    result = vision.locate(archived_crop(round_number, second))
    assert result is not None
    assert np.allclose(result, expected, atol=1)


def test_second_reference_box_cross_round(vision: BagelRouteVision) -> None:
    """第七局箱前使用第二参考图仍落在第一局全局坐标。"""
    result = vision.locate(archived_crop(7, 32, near_box=True))
    assert result is not None
    assert np.allclose(result, (113, 84), atol=2)


@pytest.mark.parametrize('round_number,second', [
    (2, 32), (3, 33), (4, 27), (5, 28), (6, 30), (8, 36), (9, 34),
])
def test_other_spawns_rejected(vision: BagelRouteVision, round_number: int, second: int) -> None:
    """其他候选出生地不能返回这条短线的位置。"""
    assert vision.locate(archived_crop(round_number, second)) is None


def test_missing_map_rejected(vision: BagelRouteVision) -> None:
    """小地图不可见时不给位置。"""
    assert vision.locate(np.zeros((201, 201, 3), np.uint8)) is None


@pytest.mark.parametrize('state,expected,tolerance,not_spawn', [
    ('保险箱转向定位失败-20260921.webp', (115.4, 81.7), 2, False),
    ('保险箱途中定位失败-20260921.webp', (149.8, 83.8), 2, False),
    ('提前左转-录像60s.webp', (110, 99.4), 2, False),
    ('提前左转完成-录像61s.webp', (110.3, 97.3), 2, False),
    ('保险箱途中-录像71s.webp', (159.8, 84.8), 2, False),
    ('保险箱途中-录像72s.webp', (182.7, 88.6), 2, False),
    ('雅努斯转角定位失败-1440缩放.webp', (118.2, 93.7), 1, True),
    *[(f'批次失败-BagelNavigate_{stamp}.webp', (118, 98), 2, True)
      for stamp in (1789884125881, 1789885044619, 1789886244451, 1789886664579, 1789887360086)],
    ('雅努斯转角-r01-41.80s.webp', (119.4, 93.6), 1, False),
    ('雅努斯转角-r07-31.25s.webp', (113.6, 97.0), 1, False),
])
def test_archived_route_positions(
    vision: BagelRouteVision, state: str, expected: tuple[float, float],
    tolerance: int, not_spawn: bool,
) -> None:
    """保留所有历史失败样本及各自误差，箱前位置不能误认出生点。"""
    crop = archived_state(state)
    position = vision.locate(crop)
    assert position is not None
    assert np.allclose(position, expected, atol=tolerance)
    if not_spawn:
        assert not vision.is_at_spawn(crop)


@pytest.mark.parametrize('state', [f'实机非A-r{index}.webp' for index in range(1, 5)])
def test_live_other_spawns_rejected(vision: BagelRouteVision, state: str) -> None:
    """实机的四次非 A 出生不能被新增转角参考误认成 A。"""
    assert vision.locate(archived_state(state)) is None
    assert not vision.is_at_spawn(archived_state(state))


def test_competing_regions_check_every_pair(
    vision: BagelRouteVision, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """前两处分区位置相同、第三处偏离时仍须拒绝，不能改图像表示绕过。"""
    image = archived_crop(1, 39)
    x, y = (100 - value for value in vision.map.origin)
    calls: list[int] = []

    def fake_matches(*_args: object) -> tuple[MinimapMatch, ...]:
        """模拟一张底图中的多个合理匹配位置。"""
        calls.append(1)
        return tuple(
            MinimapMatch(((1, 0, 0), (0, 1, 0)), (x + delta, y), 10, 10, 0)
            for delta in (0, 0, 6)
        )

    monkeypatch.setattr('zzz_od.application.bagel.bagel_map_locator.match_feature_regions', fake_matches)
    assert vision.locate(image) is None
    assert vision.last_location.reason == 'ambiguous_position'
    assert len(calls) == 1
