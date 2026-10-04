from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_safe_slots import lock_safe_suffix

from zzz_od.application.bagel.bagel_clean import BagelCleanWarehouse
from zzz_od.application.bagel.bagel_slots import WAREHOUSE_SAFE_CENTERS

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('capacity', [2, 3, 4, 5])
@pytest.mark.parametrize('unknown', [False, True])
def test_sale_requires_known_empty_unlocked_slots(
    test_context: TestContext, capacity: int, unknown: bool,
) -> None:
    """锁格允许空箱核验通过，未知格必须阻止出售。"""
    screen = lock_safe_suffix(
        test_context.load_screen('贝果-仓库', '入仓后安全箱空-r07-118s'), capacity, WAREHOUSE_SAFE_CENTERS,
    )
    if unknown:
        center = WAREHOUSE_SAFE_CENTERS[0]
        screen[center.y - 48:center.y + 48, center.x - 48:center.x + 48] = 0
    op = BagelCleanWarehouse(test_context)
    op.last_screenshot = screen
    assert op._safe_clear() is not unknown
