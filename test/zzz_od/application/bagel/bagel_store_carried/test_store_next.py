from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_loadout import (
    WatchedStore,
    paint_count,
    running_operation,
)
from test.harness.bagel_loadout import controller as controller

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_store_carried import (
    BagelStoreCarried,
)

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


@pytest.mark.parametrize('pending', [False, True])
def test_warehouse_animation_does_not_block_bulk_transfer(
    test_context: TestContext, controller: TransferController, pending: bool,
) -> None:
    """两张真实动画帧用于批量按钮；已发送输入时不得补点。"""
    before = test_context.load_screen('贝果-仓库', 'clear_carried_six_before')
    after = test_context.load_screen('贝果-仓库', 'clear_carried_six_animation')
    controller.set_phases([{'frame': after, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}])
    op = WatchedStore(test_context)
    if pending:
        op.pending = True
        op.pending_started = time.monotonic()
        op.before_counts = (6, 0, 182, 50, 280)
    with running_operation(op):
        op.last_screenshot = before
        assert op.store_next().status == ('等待转存后格子稳定' if pending else '等待仓库格子稳定')
        op.last_screenshot = after
        result = op.store_next()
        assert result.status == ('入仓操作后物品未完整转出，等待核对' if pending else '等待批量入仓结果')
        assert len(controller.recorded_clicks) == (0 if pending else 1)
        assert op.moved == 0


@pytest.mark.parametrize('change', ['unknown', 'occupied', 'count', 'layout', 'page'])
def test_warehouse_requires_consecutive_complete_observations(
    test_context: TestContext, controller: TransferController, change: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """数量、占用、布局变化及未知帧必须打断稳定记录，不能提前批量入仓。"""
    screen = test_context.load_screen('贝果-仓库', 'clear_carried_six_before')
    changed = screen.copy()
    if change == 'unknown':
        changed[320:380, 237:297] = 0
    elif change == 'occupied':
        changed[320:380, 237:297] = screen[198:258, 237:297]
        changed[198:258, 237:297] = screen[320:380, 237:297]
    elif change == 'count':
        paint_count(test_context, changed, '贝果-仓库', '仓库数量', '?')
    elif change == 'layout':
        changed[172:768, 210:850] = screen[180:776, 210:850]
    controller.set_phases([{'frame': screen, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}])
    op = WatchedStore(test_context)
    with running_operation(op):
        op.last_screenshot = screen
        assert op.store_next().status == '等待仓库格子稳定'
        op.last_screenshot = changed
        if change == 'page':
            with monkeypatch.context() as patch:
                patch.setattr(op, 'round_by_find_area', lambda *_: op.round_retry())
                assert not op.store_next().is_success
        else:
            assert not op.store_next().is_success
        op.last_screenshot = screen
        assert op.store_next().status == '等待仓库格子稳定'
        assert not controller.recorded_clicks
        op.last_screenshot = screen.copy()
        assert op.store_next().status == '等待批量入仓结果'
        assert len(controller.recorded_clicks) == 1


@pytest.mark.parametrize('state', [
    '仓库批量出售中', '仓库快速选择', '出售二次确认-20260921', '出售获得硬币-20260921',
])
@pytest.mark.parametrize('pending', [False, True])
def test_sale_state_stops_before_transfer_or_success(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, state: str, pending: bool,
) -> None:
    """空箱也不能在出售状态报告完成；转存后遇到出售界面同样停止。"""
    test_context.mock_screen('贝果-仓库', state)
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    op = BagelStoreCarried(test_context)
    op.pending = pending
    op.moved = 2
    op.screenshot()
    result = op.store_next()
    assert result.is_fail and '出售状态' in result.status
    assert op.moved == 2
    assert op._stable_image is None
    click.assert_not_called()


@pytest.mark.parametrize('pending', [False, True])
def test_empty_backpack_requires_two_verified_frames(
    test_context: TestContext, controller: TransferController, pending: bool,
) -> None:
    """真实空包与空安全箱连续两帧核验后才完成；已点击时同时核对转存数量。"""
    screen = test_context.load_screen('贝果-仓库', 'clear_loadout_prepare_warehouse_empty')
    controller.set_phases([{'frame': screen}])
    op = WatchedStore(test_context)
    if pending:
        op.pending = True
        op.pending_started = time.monotonic()
        op.before_counts = (2, 0, 186, 50, 280)
    with running_operation(op):
        op.last_screenshot = screen
        first = op.store_next()
        assert first.result == OperationRoundResultEnum.WAIT
        assert first.status == ('等待转存后格子稳定' if pending else '等待仓库格子稳定')
        op.last_screenshot = screen.copy()
        result = op.store_next()
        assert result.is_success and result.status == '携带物已全部转存'
        assert result.data == {'moved': 2 if pending else 0, 'warehouse': (188, 280)}
        assert not controller.recorded_clicks


@pytest.mark.parametrize('kind,reason', [
    ('occupied', '背包格子与占用数不符'),
    ('unknown', '背包格子状态不清'),
    ('missing_rows', '无法定位背包完整格子行'),
])
def test_invalid_zero_count_frame_breaks_empty_backpack_stability(
    test_context: TestContext, controller: TransferController, kind: str, reason: str,
) -> None:
    """零读数下出现冲突、未知或定位失败后，必须重新取得连续两张完整空包帧。"""
    empty = test_context.load_screen('贝果-仓库', 'clear_loadout_prepare_warehouse_empty')
    changed = empty.copy()
    if kind == 'occupied':
        changed = test_context.load_screen('贝果-仓库', 'clear_carried_six_before').copy()
        paint_count(test_context, changed, '贝果-仓库', '背包数量', '0/50')
    elif kind == 'unknown':
        changed[198:258, 237:297] = 0
    else:
        changed[160:780, 210:850] = 20
    controller.set_phases([{'frame': empty}])
    op = WatchedStore(test_context)
    with running_operation(op):
        op.last_screenshot = empty
        assert op.store_next().status == '等待仓库格子稳定'
        op.last_screenshot = changed
        result = op.store_next()
        assert result.result == OperationRoundResultEnum.WAIT
        assert result.status == reason
        assert op._stable_image is None
        op.last_screenshot = empty
        assert op.store_next().status == '等待仓库格子稳定'
        op.last_screenshot = empty.copy()
        assert op.store_next().is_success
        assert not controller.recorded_clicks
