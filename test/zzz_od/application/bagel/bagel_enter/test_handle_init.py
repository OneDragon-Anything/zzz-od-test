from __future__ import annotations

from typing import TYPE_CHECKING

from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_init_resets_investment_attempts(test_context: TestContext) -> None:
    """复用入场操作时不能继承上一局的归零预算或确认状态。"""
    op = BagelEnter(test_context)
    op.investment_retries = 3
    op.investment_confirmed = True
    op.zero_checked = True
    op.handle_init()
    assert op.investment_retries == 0
    assert not op.investment_confirmed
    assert not op.zero_checked
