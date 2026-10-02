from __future__ import annotations

import pytest

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_FILL,
    ACTION_SWAP,
    BagelSlotMark,
    choose_store_action,
    is_strictly_better,
)


def _mark(index: int, quality: str, item_type: str) -> BagelSlotMark:
    return BagelSlotMark(index, Point(0, 0), quality, item_type)


def test_material_is_lower_than_non_material_regardless_of_quality() -> None:
    """高品质材料也不能挤掉低品质的非材料；同类材料仍按品质排序。"""
    material = _mark(0, 'Z', '材料')
    valuable = _mark(1, 'A', '贵重物品')
    assert is_strictly_better(valuable, material)
    assert not is_strictly_better(material, valuable)
    assert is_strictly_better(material, _mark(2, 'S', '材料'))
    fill = choose_store_action([material, valuable], [], [0])
    assert fill is not None and fill.source_index == 1
    swap = choose_store_action([valuable], [material], [])
    assert swap is not None and swap.kind == ACTION_SWAP


def test_fill_empty_safe_with_best_result() -> None:
    """有空安全箱时把当前最好的结果装入最左空格，未知也可入。"""
    results = [
        _mark(0, 'A', '战术道具'),
        _mark(1, 'S', '战术棱镜'),
        _mark(2, '?', '其他'),
    ]
    choice = choose_store_action(results, [], [0, 1, 2, 3, 4])
    assert choice is not None
    assert choice.kind == ACTION_FILL
    assert choice.source_index == 1
    assert choice.dest_index == 0
    unknown = choose_store_action([_mark(4, '?', '其他')], [], [2])
    assert unknown is not None
    assert unknown.kind == ACTION_FILL
    assert unknown.dest_index == 2


def test_swap_when_result_strictly_better_than_worst_safe() -> None:
    """箱满时只对换严格更优的一件，目标为箱内最差格。"""
    results = [_mark(3, 'S', '战术道具')]
    safes = [
        _mark(0, 'A', '贵重物品'),
        _mark(1, 'A', '战术道具'),
        _mark(2, 'S', '战术棱镜'),
        _mark(3, 'A', '其他'),
        _mark(4, 'A', '装备'),
    ]
    choice = choose_store_action(results, safes, [])
    assert choice is not None
    assert choice.kind == ACTION_SWAP
    assert choice.source_index == 3
    assert choice.dest_index == 3


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
        for lower_quality in qualities[index + 1:]:
            lower = _mark(1, lower_quality, '贵重物品')
            assert is_strictly_better(higher, lower)
            assert not is_strictly_better(lower, higher)


def test_currency_is_never_selected() -> None:
    """结果同时有金币和物品时只选物品，只有金币时不执行拖拽。"""
    currency = _mark(0, 'S', '金币')
    valuable = _mark(1, 'S', '贵重物品')
    choice = choose_store_action([currency, valuable], [], [0])
    assert choice is not None and choice.source_index == 1
    assert choose_store_action([currency], [], [0]) is None


@pytest.mark.parametrize('item_types', [('材料', '材料'), ('其他',)], ids=['materials', 'other'])
def test_full_safe_leaves_lower_priority_results(item_types: tuple[str, ...]) -> None:
    """安全箱已满时，材料和其他低优先级物品都留在搜索格。"""
    results = [_mark(index, 'A', item_type) for index, item_type in enumerate(item_types)]
    safes = [_mark(i, 'S', '贵重物品') for i in range(5)]
    assert choose_store_action(results, safes, []) is None
