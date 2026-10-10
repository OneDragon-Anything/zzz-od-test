from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse


def test_three_rounds_sell_second_and_final_only(
    config: BagelConfig, record: BagelRunRecord, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """每局重建结算操作仍跨局累计；第二局到期，第三局正常结束补卖。"""
    config.sell_interval = 2
    config.max_success_rounds = 3
    decisions: list[bool] = []

    def execute(op: BagelSettleWarehouse) -> OperationResult:
        due = getattr(op, 'sell_due', True)
        decisions.append(due)
        return OperationResult(True, BagelDeposit.STATUS_DONE, data={'sale_completed': due})

    monkeypatch.setattr(BagelSettleWarehouse, 'execute', execute)
    app = BagelApp(MagicMock(), config, record)
    for _ in range(3):
        assert app.settle().is_success
    assert decisions == [False, True, True]
    assert app.success_rounds == 3
    assert app.rounds_since_sell == 0


def test_failure_deposit_counts_but_empty_does_not(
    config: BagelConfig, record: BagelRunRecord, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失败入仓计出售间隔，空箱不计；失败终止不会触发正常结束补卖。"""
    config.sell_interval = 3
    config.max_success_rounds = 1
    statuses = iter([BagelDeposit.STATUS_DONE, BagelDeposit.STATUS_EMPTY, BagelDeposit.STATUS_DONE])
    decisions: list[bool] = []

    def execute(op: BagelSettleWarehouse) -> OperationResult:
        due = getattr(op, 'sell_due', True)
        decisions.append(due)
        return OperationResult(True, next(statuses), data={'sale_completed': False})

    monkeypatch.setattr(BagelSettleWarehouse, 'execute', execute)
    app = BagelApp(MagicMock(), config, record)
    assert app.settle_after_defeat().is_success
    assert app.settle_after_defeat().is_success
    assert app.settle_after_defeat().is_success
    assert decisions == [False, False, False]
    assert app.rounds_since_sell == 2 and app.success_rounds == 0
    app.handle_init()
    assert app.rounds_since_sell == 0


def test_failed_settlement_does_not_reset_count(
    config: BagelConfig, record: BagelRunRecord, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """出售失败不清零，也不增加成功次数。"""
    app = BagelApp(MagicMock(), config, record)
    app.rounds_since_sell = 2
    monkeypatch.setattr(BagelSettleWarehouse, 'execute',
                        lambda _: OperationResult(False, '筛选失败'))
    assert app.settle().is_fail
    assert app.rounds_since_sell == 2 and app.success_rounds == 0
