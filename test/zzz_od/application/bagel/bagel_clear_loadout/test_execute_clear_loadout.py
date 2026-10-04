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
from zzz_od.application.bagel.bagel_store_carried import (
    WAREHOUSE_SAFE_CENTERS,
)

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


def test_complete_clear_flow(test_context: TestContext, controller: TransferController) -> None:
    """完整跑图验证先清内容物、逐格卸装、返回备战并全零；不点前往空洞。"""
    warehouse = warehouse_frames(test_context)
    equipment = unload_frames(test_context)
    controller.set_phases([
        {'frame': ('贝果-备战', 'clear_loadout_carried'), 'exit': ('on_click_in', [180, 980, 450, 1060])},
        {'frame': warehouse[0], 'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': warehouse[2], 'exit': ('on_click_in', '菜单', '返回')},
        *[{'frame': equipment[i], 'exit': ('transfer', center)} for i, center in enumerate(LOADOUT_CENTERS)],
        {'frame': equipment[-1]},
    ])
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 12
        assert len(controller.recorded_clicks) == 23  # 导航两下、批量入仓一下、十件装备各两下。
        assert controller.phase_idx == 23
        assert not controller.recorded_scrolls


@pytest.mark.parametrize('start_index', [0, 6])
def test_empty_containers_skip_warehouse_and_unload(
    test_context: TestContext, controller: TransferController, start_index: int,
) -> None:
    """背包 0/50 或 0/20 且安全箱为空时，完整流程只点击已装备槽。"""
    frames = unload_frames(test_context)
    centers = LOADOUT_CENTERS[start_index:]
    controller.set_phases([
        *[{'frame': frames[i], 'exit': ('transfer', LOADOUT_CENTERS[i])}
          for i in range(start_index, len(LOADOUT_CENTERS))],
        {'frame': frames[-1]},
    ])
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success and result.status == '战备已全部清空'
        assert result.data['moved'] == len(centers)
        assert [pos.tuple() for pos in controller.recorded_clicks] == [
            center.tuple() for center in centers for _ in range(2)
        ]


def test_empty_backpack_with_safe_item_still_visits_warehouse(
    test_context: TestContext, controller: TransferController,
) -> None:
    """背包空但安全箱非空时仍先批量转存，再卸下剩余道具。"""
    equipment = unload_frames(test_context)
    prepare = equipment[-2].copy()
    paint_count(test_context, prepare, '贝果-备战', '安全箱数量', '1/5')
    warehouse = warehouse_frames(test_context)
    before, after = warehouse[2].copy(), warehouse[2].copy()
    x, y = WAREHOUSE_SAFE_CENTERS[0].tuple()
    before[y-40:y+40, x-40:x+40] = warehouse[0][187:267, 227:307]
    for screen in (before, after):
        paint_count(test_context, screen, '贝果-仓库', '背包数量', '0/20')
    controller.set_phases([
        {'frame': prepare, 'exit': ('on_click_in', [180, 980, 450, 1060])},
        {'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': after, 'exit': ('on_click_in', '菜单', '返回')},
        {'frame': equipment[-2], 'exit': ('transfer', LOADOUT_CENTERS[-1])},
        {'frame': equipment[-1]},
    ])
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 2
        assert len(controller.recorded_clicks) == 5
        assert controller.phase_idx == 5


def test_unknown_prepare_never_clicks(
    test_context: TestContext, controller: TransferController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有一项未知时先重读，持续失败也不会清空其它已识别物品。"""
    controller.set_phases([{'frame': ('贝果-备战', 'clear_loadout_carried')}])
    monkeypatch.setattr('zzz_od.application.bagel.bagel_clear_loadout.read_loadout', MagicMock(return_value={}))
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert not result.success and '五项携带识别不完整' in result.status
        assert not controller.recorded_clicks


def test_no_room_for_equipment_stops_in_warehouse(
    test_context: TestContext, controller: TransferController,
) -> None:
    """内容物虽已转存，剩余空位不足时不能再尝试卸装或出售。"""
    warehouse = warehouse_frames(test_context)[2].copy()
    paint_count(test_context, warehouse, '贝果-仓库', '仓库数量', '279/280')
    prepare = test_context.load_screen('贝果-备战', 'clear_loadout_tools_only').copy()
    paint_count(test_context, prepare, '贝果-备战', '背包数量', '2/20')
    backpack_view = prepare.copy()
    backpack_view[:, :960] = test_context.load_screen('贝果-备战', 'clear_loadout_carried')[:, :960]
    controller.set_phases([
        {'frame': prepare, 'exit': ('on_click_in', [1490, 800, 1620, 850])},
        # 模拟切回背包视图后出现前往仓库，再进入只有一个空位的仓库。
        {'frame': backpack_view, 'exit': ('on_click_in', [180, 980, 450, 1060])},
        {'frame': warehouse},
    ])
    op = WatchedClear(test_context)
    with running_operation(op):
        result = op.execute()
        assert not result.success and '仓库空位不足' in result.status
        assert len(controller.recorded_clicks) == 2
