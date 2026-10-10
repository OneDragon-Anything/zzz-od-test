from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_clean import BagelCleanWarehouse
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse
from zzz_od.application.bagel.bagel_store_carried import BagelStoreCarried

if TYPE_CHECKING:
    from test.conftest import TestContext


class WatchedSettle(WatchdogOperationMixin, BagelSettleWarehouse):
    """限制结算节点轮数，避免断边或等待导致测试挂住。"""

    watchdog_max_rounds: int = 20


@pytest.mark.parametrize('starting', [False, True])
@pytest.mark.parametrize('post_sale_full', [False, True])
@pytest.mark.parametrize('first,second,auto_clean,due,full,expected_events,success', [
    (BagelDeposit.STATUS_DONE, None, True, False, False, ['deposit'], True),
    (BagelDeposit.STATUS_DONE, None, True, True, False, ['deposit', 'sale'], True),
    (BagelDeposit.STATUS_DONE, None, True, False, True, ['deposit', 'sale'], True),
    (BagelDeposit.STATUS_EMPTY, None, True, True, False, ['deposit'], True),
    (BagelDeposit.STATUS_EMPTY, None, True, True, True, ['deposit'], True),
    (BagelDeposit.STATUS_DONE, None, False, False, True, ['deposit'], True),
    (BagelDeposit.STATUS_FULL, None, False, True, True, ['deposit'], False),
    (BagelDeposit.STATUS_FULL, BagelDeposit.STATUS_DONE, True, False, True, ['deposit', 'sale', 'retry'], True),
    (BagelDeposit.STATUS_FULL, BagelDeposit.STATUS_EMPTY, True, False, True, ['deposit', 'sale', 'retry'], True),
    (BagelDeposit.STATUS_FULL, BagelDeposit.STATUS_FULL, True, True, True, ['deposit', 'sale', 'retry'], False),
])
def test_settlement_limits_sale_and_deposit_retry(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, first: str, second: str | None,
    auto_clean: bool, due: bool, full: bool, expected_events: list[str], success: bool, starting: bool,
    post_sale_full: bool,
) -> None:
    """真实操作图最多一次出售和一次再入仓，空箱永不出售，末尾容量仍核验。"""
    events: list[str] = []
    statuses = iter([first, second])
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': ('贝果-仓库', '空局仓库-原生1080')}])

    def deposit(op: BagelDeposit) -> OperationResult:
        events.append('retry' if events else 'deposit')
        assert op.return_on_remaining
        if len(events) > 1:
            assert op.click_when_empty
        status = next(statuses)
        return OperationResult(True, status, data={'moved': int(status == BagelDeposit.STATUS_DONE)})

    def sale(op: BagelCleanWarehouse) -> OperationResult:
        events.append('sale')
        assert op.allow_safe_items == (first == BagelDeposit.STATUS_FULL)
        return OperationResult(True, BagelCleanWarehouse.STATUS_SKIPPED)

    monkeypatch.setattr(BagelDeposit, 'execute', deposit)
    monkeypatch.setattr(BagelCleanWarehouse, 'execute', sale)
    monkeypatch.setattr(BagelStoreCarried, 'execute', deposit)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_screen.parse_capacity_pair',
                        lambda _: (280 if full and ('sale' not in events or post_sale_full) else 279, 280))
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    op = WatchedSettle(test_context, auto_clean, sell_due=due, starting=starting)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success == success, result.status
        assert events == expected_events
        if success:
            assert result.data['sale_completed'] == ('sale' in events)
    finally:
        reset_running_state(test_context, op)
