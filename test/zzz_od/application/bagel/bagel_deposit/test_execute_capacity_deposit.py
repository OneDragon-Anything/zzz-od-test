from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.bagel_safe_slots import lock_safe_suffix
from test.harness.fixture_controller import WatchdogOperationMixin

from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_slots import WAREHOUSE_SAFE_CENTERS

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


class WatchedDeposit(WatchdogOperationMixin, BagelDeposit):
    """限制仓库回读轮数。"""

    watchdog_max_rounds: int = 20


@pytest.mark.parametrize(
    'capacity',
    [
        2,
    ],
)
def test_deposit_counts_only_unlocked_items_and_confirms_empty(
    test_context: TestContext,
    controller: TransferController,
    capacity: int,
) -> None:
    """在仓库实拍中合成锁格，完整验证点击、清空与搬运计数。"""
    before = lock_safe_suffix(
        test_context.load_screen('贝果-仓库', '带物资仓库-r07-117s'),
        capacity,
        WAREHOUSE_SAFE_CENTERS,
    )
    after = lock_safe_suffix(
        test_context.load_screen('贝果-仓库', '入仓后安全箱空-r07-118s'),
        capacity,
        WAREHOUSE_SAFE_CENTERS,
    )
    controller.set_phases(
        [
            {'frame': before, 'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
            {'frame': after},
        ]
    )
    op = WatchedDeposit(test_context)
    with running_operation(op):
        result = op.execute()
    assert result.success, result.status
    assert result.status == op.STATUS_DONE
    assert result.data['moved'] == capacity
    assert len(controller.recorded_clicks) == 1


@pytest.mark.parametrize(
    'settlement',
    [
        False,
        True,
    ],
)
def test_full_warehouse_stack_deposit_preserves_tool_guard(
    test_context: TestContext,
    controller: TransferController,
    monkeypatch: pytest.MonkeyPatch,
    settlement: bool,
) -> None:
    """正式结算允许满仓合并堆叠后清箱，独立入仓仍保留原保护。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
                'exit': ('on_click_in', '贝果-仓库', '放入仓库'),
            },
            {'frame': ('贝果-仓库', '入仓后安全箱空-r07-118s')},
        ]
    )
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_deposit.read_area', lambda *_: '全部(280/280)'
    )
    op = WatchedDeposit(test_context, return_on_remaining=settlement)
    with running_operation(op):
        result = op.execute()
    assert result.success == settlement, result.status
    assert len(controller.recorded_clicks) == 1
    if settlement:
        assert result.status == op.STATUS_DONE
        assert result.data['warehouse_before'] == result.data['warehouse_after'] == 280
        assert result.data['moved'] > 0
    else:
        assert '不能证明物资已入仓' in result.status
