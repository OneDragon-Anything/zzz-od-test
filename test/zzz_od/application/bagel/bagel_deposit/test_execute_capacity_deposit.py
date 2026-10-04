from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.bagel_safe_slots import lock_safe_suffix
from test.harness.fixture_controller import WatchdogOperationMixin

from zzz_od.application.bagel.bagel_deposit import BagelDeposit

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


class WatchedDeposit(WatchdogOperationMixin, BagelDeposit):
    """限制仓库回读轮数。"""

    watchdog_max_rounds: int = 20


@pytest.mark.parametrize('capacity', [2, 3, 4, 5])
def test_deposit_counts_only_unlocked_items_and_confirms_empty(
    test_context: TestContext, controller: TransferController, capacity: int,
) -> None:
    """在仓库实拍中合成锁格，完整验证点击、清空与搬运计数。"""
    before = lock_safe_suffix(test_context.load_screen('贝果-仓库', '带物资仓库-r07-117s'), capacity)
    after = lock_safe_suffix(test_context.load_screen('贝果-仓库', '入仓后安全箱空-r07-118s'), capacity)
    controller.set_phases([
        {'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': after},
    ])
    op = WatchedDeposit(test_context)
    with running_operation(op):
        result = op.execute()
    assert result.success, result.status
    assert result.status == op.STATUS_DONE
    assert result.data['moved'] == capacity
    assert len(controller.recorded_clicks) == 1


@pytest.mark.parametrize('after_click', [False, True])
def test_unknown_safe_never_reports_deposit_success(
    test_context: TestContext, controller: TransferController, after_click: bool,
) -> None:
    """点击前未知不操作，点击后未知不补点也不记成功。"""
    before = lock_safe_suffix(test_context.load_screen('贝果-仓库', '带物资仓库-r07-117s'), 4)
    unknown = before.copy()
    unknown[851:947, 312:408] = 0
    phases = [{'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')}] if after_click else []
    controller.set_phases([*phases, {'frame': unknown}])
    op = WatchedDeposit(test_context)
    with running_operation(op):
        result = op.execute()
    assert not result.success and '状态不明' in result.status
    assert len(controller.recorded_clicks) == int(after_click)
