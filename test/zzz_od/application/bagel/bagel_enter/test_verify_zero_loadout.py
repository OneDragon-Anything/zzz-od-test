from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('allowed', [False, True])
def test_nonzero_only_routes_first_entry_to_clear(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, allowed: bool,
) -> None:
    """非零进入清空分支时不直接点击前往空洞，也不提前设置已核验。"""
    test_context.mock_screen('贝果-备战', 'clear_loadout_carried')
    op = BagelEnter(test_context, allow_clear_loadout=allowed)
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    op.screenshot()
    result = op.verify_zero_loadout()
    assert result.is_success is allowed
    assert not op.zero_checked
    if allowed:
        assert result.status == '需要清空启动战备'
    else:
        assert result.is_fail
    click.assert_not_called()
