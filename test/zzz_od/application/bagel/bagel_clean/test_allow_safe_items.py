from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from zzz_od.application.bagel.bagel_clean import BagelCleanWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('safe_after,warehouse_after,success', [
    ((0,), 279, True), ((), 280, True), ((0,), 280, False), ((1,), 279, False),
    (None, 279, False), ((), 281, False),
])
def test_sale_recovery_requires_observed_progress(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    safe_after: tuple[int, ...] | None, warehouse_after: int, success: bool,
) -> None:
    """允许残留出售时仍须看到腾位或安全箱减少，未知、新增占用不放行。"""
    op = BagelCleanWarehouse(test_context, allow_safe_items=True)
    op._safe_before = (0,)
    op._warehouse_before = 280
    monkeypatch.setattr(op, '_warehouse_idle', lambda: True)
    monkeypatch.setattr(op, '_warehouse_count', lambda: warehouse_after)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_clean.safe_occupied_indices', lambda _: safe_after)
    assert op.wait_idle_after_sell().is_success == success


@pytest.mark.parametrize('allow,occupied,success', [(False, (0,), False), (True, (0,), True), (True, None, False)])
def test_only_authorized_known_safe_items_can_enter_sale(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    allow: bool, occupied: tuple[int, ...] | None, success: bool,
) -> None:
    """独立出售仍禁止安全箱有物；授权残留出售也不能绕过未知状态。"""
    op = BagelCleanWarehouse(test_context, allow_safe_items=allow)
    monkeypatch.setattr(op, '_warehouse_idle', lambda: True)
    monkeypatch.setattr(op, '_warehouse_count', lambda: 280)
    monkeypatch.setattr(op, '_has_area', lambda _: True)
    monkeypatch.setattr(op, '_in_filter', lambda: False)
    monkeypatch.setattr(op, '_in_sell_mode', lambda: False)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_clean.safe_occupied_indices', lambda _: occupied)
    monkeypatch.setattr(op, 'round_by_find_and_click_area', lambda *_args, **_kwargs: op.round_success())
    assert op.open_sell().is_success == success
