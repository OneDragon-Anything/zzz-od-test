"""录像店复活点出生判据同时检查匹配与位置。"""

from test.zzz_od.application.bagel.bagel_route_vision.conftest import archived_crop

from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision


def test_spawn_not_entire_route(vision: BagelRouteVision) -> None:
    """路线末端可定位，但不能再次算作 A 出生。"""
    assert vision.is_at_spawn(archived_crop(7, 30))
    assert not vision.is_at_spawn(archived_crop(7, 32, near_box=True))
    assert not vision.is_at_spawn(archived_crop(2, 32))
