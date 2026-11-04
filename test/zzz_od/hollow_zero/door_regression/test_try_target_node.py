from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import (
    HollowZeroMap,
    HollowZeroMapNode,
)


@pytest.mark.parametrize('name', ['门扉禁闭-财富', '门扉禁闭-善战', '门扉禁闭-侵蚀'])
def test_door_limit_is_per_position(door_context: SimpleNamespace, name: str) -> None:
    """已尝试的门不能由方向兜底重选，也不能影响别处的同类型门。"""
    context = door_context.withered_domain
    entry = context.data_service.name_2_entry[name]
    door = HollowZeroMapNode(Rect(100, 0, 200, 100), entry)
    current_map = HollowZeroMap([door], None, {})
    assert context.try_target_node(current_map, door) is door
    context.update_context_after_move(current_map, door, update_current=False)
    assert context.try_target_node(current_map, door) is door
    assert door.path_go_way == 1
    context.update_context_after_move(current_map, door, update_current=False)
    assert context.try_target_node(current_map, door) is None
    other = HollowZeroMapNode(Rect(300, 0, 400, 100), entry)
    assert context.try_target_node(current_map, other) is other
