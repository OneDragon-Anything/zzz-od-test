from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.hollow_zero.event.door_battle import DoorBattle
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import (
    HollowZeroMap,
    HollowZeroMapNode,
)
from zzz_od.hollow_zero.hollow_runner import HollowRunner


def make_map(ctx: SimpleNamespace, door_name: str) -> HollowZeroMap:
    """构造当前格、已通行格、门和另一条可选路径。"""
    entries = ctx.withered_domain.data_service.name_2_entry
    nodes = [
        HollowZeroMapNode(Rect(0, 0, 100, 100), entries['当前']),
        HollowZeroMapNode(Rect(100, 0, 200, 100), entries['空白已通行']),
        HollowZeroMapNode(Rect(200, 0, 300, 100), entries[door_name]),
        HollowZeroMapNode(Rect(100, 100, 200, 200), entries['齿轮硬币箱']),
    ]
    return HollowZeroMap(nodes, 0, {0: [1], 1: [0, 2, 3], 2: [1], 3: [1]})


@pytest.mark.parametrize('door_name', ['门扉禁闭-善战', '门扉禁闭-侵蚀'])
@pytest.mark.parametrize('handled', [False, True], ids=['handler-failed', 'click-but-still-closed'])
@pytest.mark.parametrize('alternative', [True, False], ids=['other-route', 'fallback'])
def test_closed_door_attempts_are_bounded(
    door_context: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
    door_name: str, handled: bool, alternative: bool,
) -> None:
    """入口处理失败或点击后门未开启时，不能在门和空白格之间循环。"""
    ctx = door_context
    # 自定义优先探索门；无其他路线时还须覆盖方向兜底绕过访问上限的情况。
    monkeypatch.setattr(ctx.withered_domain, '_get_go_in_1_step', lambda: [door_name])
    runner = HollowRunner(ctx)
    monkeypatch.setattr(runner, '_check_extra_task_finished', lambda *_: False)
    monkeypatch.setattr(runner, 'get_map_node_pos_to_click', lambda _, node: node.pos.center)
    execute = Mock(return_value=OperationResult(handled, '开门' if handled else '未匹配合适的处理方法'))
    monkeypatch.setattr(DoorBattle, 'execute', execute)
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    targets: list[str] = []
    get_next = ctx.withered_domain.get_next_to_move

    def record_target(current_map: HollowZeroMap) -> HollowZeroMapNode:
        target = get_next(current_map)
        assert target is not None
        targets.append(target.entry.entry_name)
        return target

    monkeypatch.setattr(ctx.withered_domain, 'get_next_to_move', record_target)
    for attempt in range(6):
        # 门未开，下一帧重新识别到原来的当前格和仍然关闭的门。
        current_map = make_map(ctx, door_name)
        if not alternative:
            current_map.nodes.pop()
            current_map.edges = {0: [1], 1: [0, 2], 2: [1]}
        runner.try_move_by_map(screen, float(attempt + 1), current_map)
        if targets[-1] != door_name:
            break
    assert targets == [door_name, door_name, '齿轮硬币箱' if alternative else 'fake']
    assert execute.call_count == 2
    assert ctx.withered_domain.had_been_entry(door_name)
    visited = [node for node in ctx.withered_domain._visited_nodes if node.entry.entry_name == door_name]
    assert len(visited) == 1
    assert visited[0].visited_times == 2


def test_opened_door_can_be_crossed(door_context: SimpleNamespace) -> None:
    """旧门的访问记录不能阻止同位置已经开启的门。"""
    ctx = door_context
    old_map = make_map(ctx, '门扉禁闭-善战')
    door = old_map.nodes[2]
    for _ in range(2):
        ctx.withered_domain.update_context_after_move(old_map, door, update_current=False)
    current_map = make_map(ctx, '开启的门')
    entries = ctx.withered_domain.data_service.name_2_entry
    current_map.nodes.append(HollowZeroMapNode(Rect(300, 0, 400, 100), entries['传送点']))
    current_map.edges[2].append(4)
    current_map.edges[4] = [2]
    ctx.withered_domain.get_next_to_move(current_map)
    assert current_map.nodes[2].path_step_cnt >= 0
    assert ctx.withered_domain.try_target_node(current_map, current_map.nodes[2]) is current_map.nodes[2]
    assert current_map.nodes[4].path_step_cnt >= 0
