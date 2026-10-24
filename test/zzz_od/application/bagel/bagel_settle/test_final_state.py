from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext

from test.harness.bagel_safe_slots import lock_safe_suffix

from zzz_od.application.bagel.bagel_slots import WAREHOUSE_SAFE_CENTERS


@pytest.mark.parametrize(
    'case,expected',
    [
        ('screen_missing', '等待结算后仓库画面'),
        ('safe_occupied', '结算后安全箱仍有物资'),
        ('count_missing', '结算后无法核对仓库容量'),
    ],
)
def test_final_capacity_rejects_unverified_state(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected: str,
) -> None:
    """只有安全箱为空且容量可读的仓库主画面才能完成结算。"""
    op = BagelSettleWarehouse(test_context, auto_clean=False)
    if case == 'screen_missing':
        test_context.mock_screen('贝果-研究站', '主界面-原生1080')
    elif case == 'safe_occupied':
        test_context.mock_screen('贝果-仓库', '带物资仓库-r07-117s')
    else:
        test_context.mock_screen('贝果-仓库', '空局仓库-原生1080')
        monkeypatch.setattr(
            'zzz_od.application.bagel.bagel_screen.read_area', lambda *_args: ''
        )
    op.screenshot()
    result = op.verify_warehouse_capacity()
    assert not result.is_success
    assert expected in result.status
    assert result.is_fail == (case == 'safe_occupied')


@pytest.mark.parametrize('unknown', [False, True])
def test_settlement_accepts_locks_but_rejects_unknown_safe(
    test_context: TestContext,
    unknown: bool,
) -> None:
    """结算末尾仍须区分锁格和未知格，不能仅凭没有物品结束。"""
    screen = lock_safe_suffix(
        test_context.load_screen('贝果-仓库', '入仓后安全箱空-r07-118s'),
        4,
        WAREHOUSE_SAFE_CENTERS,
    )
    if unknown:
        center = WAREHOUSE_SAFE_CENTERS[0]
        screen[center.y - 48 : center.y + 48, center.x - 48 : center.x + 48] = 0
    op = BagelSettleWarehouse(test_context, auto_clean=False)
    op.last_screenshot = screen
    result = op.verify_warehouse_capacity()
    assert result.is_success is not unknown
    if unknown:
        assert result.is_fail and '状态不明' in result.status
