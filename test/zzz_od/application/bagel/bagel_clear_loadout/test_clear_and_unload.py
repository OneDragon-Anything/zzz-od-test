from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_loadout import (
    WatchedClear,
    paint_count,
    running_operation,
    unload_frames,
    warehouse_frames,
)
from test.harness.bagel_loadout import controller as controller

from zzz_od.application.bagel.bagel_clear_loadout import (
    LOADOUT_CENTERS,
)

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController

import time


def test_complete_clear_flow(
    test_context: TestContext, controller: TransferController
) -> None:
    """完整跑图验证先清内容物、逐格卸装、返回备战并全零；不点前往空洞。"""
    warehouse = warehouse_frames(test_context)
    equipment = unload_frames(test_context)
    controller.set_phases(
        [
            {
                'frame': ('贝果-备战', 'clear_loadout_carried'),
                'exit': ('on_click_in', [180, 980, 450, 1060]),
            },
            {'frame': warehouse[0], 'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
            {'frame': warehouse[2], 'exit': ('on_click_in', '菜单', '返回')},
            *[
                {'frame': equipment[i], 'exit': ('transfer', center)}
                for i, center in enumerate(LOADOUT_CENTERS)
            ],
            {'frame': equipment[-1]},
        ]
    )
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 12
        assert (
            len(controller.recorded_clicks) == 23
        )  # 导航两下、批量入仓一下、十件装备各两下。
        assert controller.phase_idx == 23
        assert not controller.recorded_scrolls


def test_unknown_prepare_never_clicks(
    test_context: TestContext,
    controller: TransferController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有一项未知时先重读，持续失败也不会清空其它已识别物品。"""
    controller.set_phases([{'frame': ('贝果-备战', 'clear_loadout_carried')}])
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_clear_loadout.read_loadout',
        MagicMock(return_value={}),
    )
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert not result.success and '五项携带识别不完整' in result.status
        assert not controller.recorded_clicks


def test_no_room_for_equipment_stops_in_warehouse(
    test_context: TestContext,
    controller: TransferController,
) -> None:
    """内容物虽已转存，剩余空位不足时不能再尝试卸装或出售。"""
    warehouse = warehouse_frames(test_context)[2].copy()
    paint_count(test_context, warehouse, '贝果-仓库', '仓库数量', '279/280')
    prepare = test_context.load_screen('贝果-备战', 'clear_loadout_tools_only').copy()
    paint_count(test_context, prepare, '贝果-备战', '背包数量', '2/20')
    backpack_view = prepare.copy()
    backpack_view[:, :960] = test_context.load_screen(
        '贝果-备战', 'clear_loadout_carried'
    )[:, :960]
    controller.set_phases(
        [
            {'frame': prepare, 'exit': ('on_click_in', [1490, 800, 1620, 850])},
            # 模拟切回背包视图后出现前往仓库，再进入只有一个空位的仓库。
            {'frame': backpack_view, 'exit': ('on_click_in', [180, 980, 450, 1060])},
            {'frame': warehouse},
        ]
    )
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert not result.success and '仓库空位不足' in result.status
        assert len(controller.recorded_clicks) == 2


@pytest.mark.parametrize(
    'kind',
    [
        'unchanged',
        'wrong_container',
    ],
)
def test_double_click_unconfirmed_result_stops_after_allowed_retry(
    test_context: TestContext,
    controller: TransferController,
    kind: str,
) -> None:
    """无变化只重试一次；去向异常停止且不重复输入。"""
    frames = unload_frames(test_context)
    before, after = frames[-2], frames[-1].copy()
    source = LOADOUT_CENTERS[-1]
    if kind == 'unchanged':
        after = before
    else:
        paint_count(test_context, after, '贝果-备战', '背包数量', '1/20')
    phases = [{'frame': before, 'exit': ('transfer', source)}]
    if kind == 'unchanged':
        phases.append({'frame': after, 'exit': ('transfer', source)})
    phases.append({'frame': after})
    controller.set_phases(phases)
    op = WatchedClear(test_context)
    with running_operation(op):
        for _ in range(30):
            op.screenshot()
            result = op.unload_next()
            if result.is_fail:
                break
        assert result.is_fail, result.status
        assert len(controller.recorded_clicks) == (4 if kind == 'unchanged' else 2)
        assert all(pos.tuple() == source.tuple() for pos in controller.recorded_clicks)
        assert op.moved == 0


def test_pause_after_double_click_disables_retry(
    test_context: TestContext,
    controller: TransferController,
) -> None:
    """双击后暂停过，即使画面未变也不重发输入。"""
    before = unload_frames(test_context)[-2]
    source = LOADOUT_CENTERS[-1]
    controller.set_phases(
        [{'frame': before, 'exit': ('transfer', source)}, {'frame': before}]
    )
    op = WatchedClear(test_context)
    with running_operation(op):
        op.screenshot()
        op.unload_next()
        op.screenshot()
        assert '双击转入仓库' in op.unload_next().status
        op.handle_pause()
        op.handle_resume()
        for _ in range(15):
            op.screenshot()
            result = op.unload_next()
            if result.is_fail:
                break
        assert result.is_fail, result.status
        assert len(controller.recorded_clicks) == 2
        assert op.moved == 0


@pytest.mark.parametrize(
    'change',
    [
        'value',
        'unknown',
    ],
)
def test_unload_still_rejects_unstable_or_unknown_observation(
    test_context: TestContext,
    controller: TransferController,
    change: str,
) -> None:
    """读数不稳定或槽位未知时，不得报告转存完成。"""
    after = test_context.load_screen('贝果-备战', 'clear_loadout_second_weapon_stored')
    previous = after.copy()
    if change == 'value':
        paint_count(test_context, previous, '贝果-备战', '武备价值', '180000')
    else:
        x, y = LOADOUT_CENTERS[1].tuple()
        previous[y - 32 : y + 32, x - 32 : x + 32] = 0
    controller.set_phases([{'frame': after}])
    op = WatchedClear(test_context)
    op.pending = True
    op.pending_center = LOADOUT_CENTERS[1]
    op.pending_group = '武备价值'
    op.before_values = {
        '武备价值': '180000',
        '装备价值': '160000',
        '道具价值': '78000',
        '背包数量': '0/50',
        '安全箱数量': '0/5',
    }
    op.pending_started = time.monotonic()
    op.last_screenshot = after
    assert op.unload_next().status == '等待卸装结果稳定'
    op.last_screenshot = previous
    assert not op.unload_next().is_success
    op.last_screenshot = after
    assert op.unload_next().status == '等待卸装结果稳定'
    assert op.moved == 0
    assert not controller.recorded_clicks
