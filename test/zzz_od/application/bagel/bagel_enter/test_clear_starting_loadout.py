from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_clear_loadout import BagelClearLoadout
from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_clear_requires_new_zero_check_and_never_repeats(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """子操作报告成功也必须重新读取；仍非零时不重跑清空、不入场。"""
    test_context.mock_screen('贝果-备战', 'clear_loadout_carried')
    op = BagelEnter(test_context, allow_clear_loadout=True)
    clear = MagicMock(return_value=OperationResult(True, '已清空'))
    monkeypatch.setattr(BagelClearLoadout, 'execute', clear)
    assert op.clear_starting_loadout().is_success
    assert not op.zero_checked
    assert op.verify_zero_loadout().is_fail
    assert op.clear_starting_loadout().is_fail
    clear.assert_called_once()
