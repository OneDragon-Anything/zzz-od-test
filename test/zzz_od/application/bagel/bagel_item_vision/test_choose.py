from __future__ import annotations

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_SWAP,
    BagelSlotMark,
    choose_store_action,
    is_strictly_better,
)


def _mark(index: int, quality: str, item_type: str) -> BagelSlotMark:
    return BagelSlotMark(index, Point(0, 0), quality, item_type)


def test_same_quality_uses_hardcoded_type_order() -> None:
    """同品质按写死类型顺序，相等则不换。"""
    prism = _mark(0, 'S', '战术棱镜')
    tactic = _mark(1, 'S', '战术道具')
    assert is_strictly_better(prism, tactic)
    assert not is_strictly_better(tactic, tactic)
    choice = choose_store_action(
        [_mark(2, 'S', '贵重物品')],
        [_mark(0, 'S', '战术棱镜')],
        [],
    )
    assert choice is not None
    assert choice.kind == ACTION_SWAP
    equal_choice = choose_store_action(
        [_mark(2, 'S', '战术棱镜')],
        [_mark(0, 'S', '战术棱镜')],
        [],
    )
    assert equal_choice is None


def test_all_known_qualities_outrank_lower_qualities_and_unknown() -> None:
    """非材料先比完整品质顺序，不能因低品质物品类型更优而倒置。"""
    qualities = ('Z', 'S', 'A', 'B', 'C', '?')
    for index, quality in enumerate(qualities[:-1]):
        higher = _mark(0, quality, '战术道具')
        for lower_quality in qualities[index + 1 :]:
            lower = _mark(1, lower_quality, '贵重物品')
            assert is_strictly_better(higher, lower)
            assert not is_strictly_better(lower, higher)
