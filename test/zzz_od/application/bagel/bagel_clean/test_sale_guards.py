from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from zzz_od.application.bagel.bagel_clean import BagelCleanWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext

from test.harness.bagel_safe_slots import lock_safe_suffix

from zzz_od.application.bagel.bagel_slots import WAREHOUSE_SAFE_CENTERS


@pytest.mark.parametrize(
    'allow,occupied,success',
    [
        (False, (0,), False),
        (True, (0,), True),
        (True, None, False),
    ],
)
def test_only_authorized_known_safe_items_can_enter_sale(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    allow: bool,
    occupied: tuple[int, ...] | None,
    success: bool,
) -> None:
    """独立出售仍禁止安全箱有物；授权残留出售也不能绕过未知状态。"""
    op = BagelCleanWarehouse(test_context, allow_safe_items=allow)
    monkeypatch.setattr(op, '_warehouse_idle', lambda: True)
    monkeypatch.setattr(op, '_warehouse_count', lambda: 280)
    monkeypatch.setattr(op, '_has_area', lambda _: True)
    monkeypatch.setattr(op, '_in_filter', lambda: False)
    monkeypatch.setattr(op, '_in_sell_mode', lambda: False)
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_clean.safe_occupied_indices', lambda _: occupied
    )
    monkeypatch.setattr(
        op, 'round_by_find_and_click_area', lambda *_args, **_kwargs: op.round_success()
    )
    assert op.open_sell().is_success == success


@pytest.mark.parametrize(
    'unknown,capacity',
    [
        (False, 2),
        (True, 5),
    ],
)
def test_sale_requires_known_empty_unlocked_slots(
    test_context: TestContext,
    capacity: int,
    unknown: bool,
) -> None:
    """锁格允许空箱核验通过，未知格必须阻止出售。"""
    screen = lock_safe_suffix(
        test_context.load_screen('贝果-仓库', '入仓后安全箱空-r07-118s'),
        capacity,
        WAREHOUSE_SAFE_CENTERS,
    )
    if unknown:
        center = WAREHOUSE_SAFE_CENTERS[0]
        screen[center.y - 48 : center.y + 48, center.x - 48 : center.x + 48] = 0
    op = BagelCleanWarehouse(test_context)
    op.last_screenshot = screen
    assert op._safe_clear() is not unknown
