from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import (
    WatchedStore,
    paint_count,
    running_operation,
    warehouse_frames,
)
from test.harness.bagel_loadout import controller as controller

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_store_carried import (
    WAREHOUSE_SAFE_CENTERS,
)

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


@pytest.mark.parametrize('safe', [False, True])
def test_bulk_transfer_and_stacking(
    test_context: TestContext, controller: TransferController, safe: bool,
) -> None:
    """一次批量按钮清空背包和安全箱；已有堆叠允许仓库占用不变。"""
    before, _, done = warehouse_frames(test_context)
    before, done = before.copy(), done.copy()
    paint_count(test_context, done, '贝果-仓库', '仓库数量', '186/280')
    if safe:
        x, y = WAREHOUSE_SAFE_CENTERS[0].tuple()
        before[y-40:y+40, x-40:x+40] = before[187:267, 227:307]
    controller.set_phases([
        {'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}, {'frame': done},
    ])
    op = WatchedStore(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == (3 if safe else 2)
        assert len(controller.recorded_clicks) == 1
        assert not controller.recorded_scrolls


@pytest.mark.parametrize('kind', ['unchanged', 'partial', 'warehouse_decreased', 'wrong_container', 'capacity'])
def test_unconfirmed_bulk_transfer_stops_without_reclick(
    test_context: TestContext, controller: TransferController, kind: str,
) -> None:
    """无变化、部分入仓、数量异常均停止；批量按钮始终只点一次。"""
    frames = warehouse_frames(test_context)
    after = frames[0].copy() if kind == 'unchanged' else frames[1].copy()
    if kind == 'warehouse_decreased':
        paint_count(test_context, after, '贝果-仓库', '仓库数量', '185/280')
    elif kind == 'wrong_container':
        x, y = WAREHOUSE_SAFE_CENTERS[0].tuple()
        after[y-40:y+40, x-40:x+40] = frames[0][187:267, 227:307]
    elif kind == 'capacity':
        paint_count(test_context, after, '贝果-仓库', '背包数量', '1/20')
    controller.set_phases([
        {'frame': frames[0], 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}, {'frame': after},
    ])
    op = WatchedStore(test_context)
    with running_operation(op):
        result = op.execute()
        assert not result.success
        assert len(controller.recorded_clicks) == 1
        assert op.moved == (1 if kind == 'partial' else 0)


def test_full_warehouse_does_not_click(test_context: TestContext, controller: TransferController) -> None:
    """满仓不出售腾位，也不尝试批量入仓。"""
    screen = warehouse_frames(test_context)[0].copy()
    paint_count(test_context, screen, '贝果-仓库', '仓库数量', '280/280')
    controller.set_phases([{'frame': screen}])
    op = WatchedStore(test_context)
    with running_operation(op):
        result = op.execute()
        assert not result.success and '仓库已满' in result.status
        assert not controller.recorded_clicks


def test_offscreen_items_use_bulk_button_without_scrolling(
    test_context: TestContext, controller: TransferController,
) -> None:
    """总占用非零但物品不在可见页时仍直接批量入仓，无须翻页。"""
    done = warehouse_frames(test_context)[2]
    offscreen = done.copy()
    paint_count(test_context, offscreen, '贝果-仓库', '背包数量', '6/50')
    controller.set_phases([
        {'frame': offscreen, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}, {'frame': done},
    ])
    op = WatchedStore(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 6
        assert not controller.recorded_scrolls
        assert len(controller.recorded_clicks) == 1


def test_settlement_only_moves_safe_item_not_reward(
    test_context: TestContext, controller: TransferController,
) -> None:
    """带撤离奖励的仓库仍只转存安全箱；奖励由原有返回流程处理。"""
    before = test_context.load_screen('贝果-仓库', '满仓安全箱余一件-20260924').copy()
    paint_count(test_context, before, '贝果-仓库', '仓库数量', '279/280')
    after = before.copy()
    source = WAREHOUSE_SAFE_CENTERS[4]
    x, y = source.tuple()
    after[y-40:y+40, x-40:x+40] = before[857:937, 227:307]
    paint_count(test_context, after, '贝果-仓库', '仓库数量', '280/280')
    controller.set_phases([{'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}, {'frame': after}])
    op = WatchedStore(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 1
        assert len(controller.recorded_clicks) == 1
        assert controller.recorded_clicks[0].tuple() != source.tuple()


def test_bulk_result_can_arrive_late(
    test_context: TestContext, controller: TransferController,
) -> None:
    """批量按钮点击后短暂旧帧只等待，结果出现后核验完成，不补点。"""
    before, _, after = warehouse_frames(test_context)
    controller.set_phases([
        {'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': before, 'exit': ('on_polls', 2)}, {'frame': after},
    ])
    op = WatchedStore(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 2
        assert len(controller.recorded_clicks) == 1


def test_pause_after_storage_click_only_checks_result(
    test_context: TestContext, controller: TransferController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """批量按钮点击后暂停恢复，仅核对结果，不再次点击。"""
    before, _, after = warehouse_frames(test_context)
    controller.set_phases([
        {'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}, {'frame': after},
    ])
    op = WatchedStore(test_context)
    original = controller.click

    def pause_click(pos: Point, press_time: float = 0, **kwargs: object) -> bool:
        """按钮点击后模拟暂停并恢复。"""
        result = original(pos, press_time, **kwargs)
        op.handle_pause()
        op.handle_resume()
        return result

    monkeypatch.setattr(controller, 'click', pause_click)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 2
        assert len(controller.recorded_clicks) == 1
