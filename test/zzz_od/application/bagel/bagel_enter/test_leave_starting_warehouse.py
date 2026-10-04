from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_store_carried import BagelStoreCarried

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_restart_in_prepare_warehouse_returns_after_store(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """清空中途停在备战仓库，下次启动可以转存剩余后返回备战。"""
    test_context.mock_screen('贝果-仓库', 'clear_loadout_prepare_warehouse_empty')
    op = BagelEnter(test_context, allow_clear_loadout=True)
    stored = MagicMock(return_value=OperationResult(True, '携带物已全部转存'))
    returned = MagicMock()
    monkeypatch.setattr(BagelStoreCarried, 'execute', stored)
    monkeypatch.setattr(BagelReturn, 'execute', returned)
    op.screenshot()
    assert op.handle_starting_warehouse().status == '启动仓库返回'
    stored.assert_called_once()
    returned.assert_not_called()
    click = MagicMock(return_value=True)
    monkeypatch.setattr(test_context.controller, 'click', click)
    assert not op.leave_starting_warehouse().is_success
    assert op.node_clicked
    op.leave_starting_warehouse()
    click.assert_called_once()
    test_context.mock_screen('贝果-备战', 'clear_loadout_empty')
    op.screenshot()
    assert op.leave_starting_warehouse().is_success
