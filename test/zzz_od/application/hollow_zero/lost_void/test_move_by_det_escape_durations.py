"""LostVoidMoveByDet.get_escape_durations 纯逻辑测试(smart_escape 脱困时长)。

源码在 ``lost_void_move_by_det.py``。挑战配置开启 ``smart_escape`` 时,脱困按「后退 → 横移 → 前进」执行,
后退和前进时长随本层卡住次数增长:每多卡一次后退多 0.5 秒、前进多 0.2 秒,各自最长 2 秒;第 0 次不后退不前进。
"""
import pytest

from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    LostVoidMoveByDet,
)


def test_first_escape_has_no_back_or_forward() -> None:
    assert LostVoidMoveByDet.get_escape_durations(0) == (0.0, 0.0)


def test_escape_durations_grow_with_stuck_times() -> None:
    assert LostVoidMoveByDet.get_escape_durations(1) == (0.5, 0.2)
    assert LostVoidMoveByDet.get_escape_durations(3) == pytest.approx((1.5, 0.6))


def test_escape_durations_are_capped() -> None:
    assert LostVoidMoveByDet.get_escape_durations(20) == (2.0, 2.0)
