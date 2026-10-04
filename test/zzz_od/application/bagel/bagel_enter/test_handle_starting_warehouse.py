from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_store_carried import BagelStoreCarried

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('allowed,stored', [(False, False), (True, False), (True, True)])
def test_starting_settlement_stores_before_return(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, allowed: bool, stored: bool,
) -> None:
    """首次结算起点可恢复，只有转存成功才返回入口；不调用出售流程。"""
    test_context.mock_screen('贝果-仓库', '满仓安全箱余一件-20260924')
    op = BagelEnter(test_context, allow_clear_loadout=allowed)
    calls: list[str] = []

    def store(_: BagelStoreCarried) -> OperationResult:
        """模拟仓库转存结果。"""
        calls.append('store')
        return OperationResult(stored, '转存结果')

    def return_hub(_: BagelReturn) -> OperationResult:
        """仅允许成功转存后调用返回。"""
        calls.append('return')
        return OperationResult(True, '已到入口')

    monkeypatch.setattr(BagelStoreCarried, 'execute', store)
    monkeypatch.setattr(BagelReturn, 'execute', return_hub)
    op.screenshot()
    result = op.handle_starting_warehouse()
    assert result.is_success is (allowed and stored)
    assert calls == ([] if not allowed else ['store', 'return'] if stored else ['store'])
