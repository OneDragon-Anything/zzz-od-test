from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.bagel_safe_slots import lock_safe_suffix

from zzz_od.application.bagel.bagel_store_carried import (
    WAREHOUSE_SAFE_CENTERS,
    BagelStoreCarried,
)

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


@pytest.mark.parametrize('capacity', [2, 3, 4, 5])
@pytest.mark.parametrize('unknown', [False, True])
def test_startup_clear_distinguishes_locked_from_unknown(
    test_context: TestContext, controller: TransferController, capacity: int, unknown: bool,
) -> None:
    """空仓库中的锁格不算携带物，未知格则用完五帧预算后停止。"""
    screen = lock_safe_suffix(
        test_context.load_screen('贝果-仓库', 'clear_loadout_prepare_warehouse_empty'),
        capacity, WAREHOUSE_SAFE_CENTERS,
    )
    if unknown:
        center = WAREHOUSE_SAFE_CENTERS[0]
        screen[center.y - 48:center.y + 48, center.x - 48:center.x + 48] = 0
    controller.set_phases([{'frame': screen}])
    op = BagelStoreCarried(test_context)
    with running_operation(op):
        op.last_screenshot = screen
        result = op.store_next()
        for _ in range(4 if unknown else 1):
            result = op.store_next()
    if unknown:
        assert result.is_fail and '无法完整识别' in result.status
    else:
        assert result.is_success and result.status == '携带物已全部转存'
    assert controller.recorded_clicks == []
