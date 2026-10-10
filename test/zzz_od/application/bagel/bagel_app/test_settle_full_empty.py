"""满仓清箱结算贯穿真实操作图和应用计数，不能只放行单个核验节点。"""
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
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_clean import BagelCleanWarehouse
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext


class WatchedSettle(WatchdogOperationMixin, BagelSettleWarehouse):
    """保留真实结算图，限制测试轮数。"""

    watchdog_max_rounds: int = 20


@pytest.mark.parametrize(
    'case',
    [
        'empty',
        'remaining',
    ],
)
def test_full_empty_settlement_updates_counts_and_allows_next_round(
    test_context: TestContext, config: BagelConfig, record: BagelRunRecord,
    monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    """复现长测最后一局，最终满仓清箱也能记账继续；原本空箱仍不增加成功。"""
    config.max_success_rounds = 0
    config.sell_interval = 2
    config.auto_clean_warehouse = case != 'clean_disabled'
    first = (BagelDeposit.STATUS_EMPTY if case == 'empty'
             else BagelDeposit.STATUS_FULL if case == 'remaining' else BagelDeposit.STATUS_DONE)
    statuses = iter([first, BagelDeposit.STATUS_DONE])
    events: list[str] = []
    controller = FixtureController(test_context)
    controller.set_phases([{'frame': ('贝果-仓库', '空局仓库-原生1080')}])
    monkeypatch.setattr(test_context, 'controller', controller)

    def deposit(op: BagelDeposit) -> OperationResult:
        """只替换入仓输入结果，结算核验和应用记账仍执行实际实现。"""
        events.append('retry' if op.click_when_empty else 'deposit')
        assert op.return_on_remaining
        return OperationResult(True, next(statuses))

    def sale(op: BagelCleanWarehouse) -> OperationResult:
        """残留场景严格只有一次出售，允许按原方案处理安全箱物品。"""
        assert op.allow_safe_items
        events.append('sale')
        return OperationResult(True, op.STATUS_DONE)

    monkeypatch.setattr(BagelDeposit, 'execute', deposit)
    monkeypatch.setattr(BagelCleanWarehouse, 'execute', sale)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_app.BagelSettleWarehouse', WatchedSettle)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_screen.parse_capacity_pair', lambda _: (280, 280))
    app = BagelApp(test_context, config, record)
    app.success_rounds = 80
    enter_running_state(test_context)
    try:
        result = app.settle()
        assert result.is_success, result.status
        assert app.success_rounds == (80 if case == 'empty' else 81)
        assert app.empty_rounds == int(case == 'empty')
        assert app.rounds_since_sell == int(case == 'clean_disabled')
        assert app.decide_success_rounds().status == '继续入场'
        assert events == (['deposit', 'sale', 'retry'] if case == 'remaining' else ['deposit'])
    finally:
        reset_running_state(test_context, app)
