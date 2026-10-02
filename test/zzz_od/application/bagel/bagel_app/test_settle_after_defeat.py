"""失败局遵循同一套入仓清理设置，并保留核验错误。"""

from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse


@pytest.mark.parametrize('auto_clean', [True, False])
@pytest.mark.parametrize('status', [BagelDeposit.STATUS_DONE, BagelDeposit.STATUS_EMPTY])
def test_defeat_settlement_keeps_cleanup_settings(
    config: BagelConfig, record: BagelRunRecord, monkeypatch: pytest.MonkeyPatch,
    auto_clean: bool, status: str,
) -> None:
    """失败局带物或空箱都按开关和自定义筛选结算，不增加成功局数。"""
    config.auto_clean_warehouse = auto_clean
    config.clean_mode = 'custom'
    config.clean_types = ['贵重物品']
    config.clean_qualities = ['A']
    calls: list[tuple[bool, tuple[str, ...]]] = []

    def execute(op: BagelSettleWarehouse) -> OperationResult:
        """只替换游戏操作，检查实际构造参数。"""
        calls.append((op.auto_clean, op.filter_areas))
        return OperationResult(True, status)

    monkeypatch.setattr(BagelSettleWarehouse, 'execute', execute)
    app = BagelApp(MagicMock(), config, record)
    app.defeat_rounds = 1
    result = app.settle_after_defeat()
    assert result.is_success
    assert result.status == status
    assert app.defeat_rounds == 2
    assert app.success_rounds == 0
    assert calls == [(auto_clean, ('筛选-贵重物品', '筛选-A'))]
