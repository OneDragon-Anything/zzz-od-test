from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_safe_slots import lock_safe_suffix

from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse
from zzz_od.application.bagel.bagel_slots import WAREHOUSE_SAFE_CENTERS

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('unknown', [False, True])
def test_settlement_accepts_locks_but_rejects_unknown_safe(
    test_context: TestContext, unknown: bool,
) -> None:
    """结算末尾仍须区分锁格和未知格，不能仅凭没有物品结束。"""
    screen = lock_safe_suffix(
        test_context.load_screen('贝果-仓库', '入仓后安全箱空-r07-118s'), 4, WAREHOUSE_SAFE_CENTERS,
    )
    if unknown:
        center = WAREHOUSE_SAFE_CENTERS[0]
        screen[center.y - 48:center.y + 48, center.x - 48:center.x + 48] = 0
    op = BagelSettleWarehouse(test_context, auto_clean=False)
    op.last_screenshot = screen
    result = op.verify_warehouse_capacity()
    assert result.is_success is not unknown
    if unknown:
        assert result.is_fail and '状态不明' in result.status
