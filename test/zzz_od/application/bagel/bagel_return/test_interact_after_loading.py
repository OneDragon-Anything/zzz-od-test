"""返回交互必须核对当前目标和按钮。"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel.bagel_return import BagelReturn

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('missing', ['快捷手册', '接待员名称', '按键-交互', None])
def test_interaction_requires_all_markers(test_context: TestContext, monkeypatch: pytest.MonkeyPatch, missing: str | None) -> None:
    """任意判据缺失时不按 F；三项齐全时只按一次。"""
    op = BagelReturn(test_context)
    monkeypatch.setattr(op, 'round_by_find_area', lambda screen, name, area: op.round_success() if area != missing else op.round_retry())
    interact = MagicMock()
    monkeypatch.setattr(test_context.controller, 'interact', interact)
    result = op.interact_after_loading()
    assert result.is_success == (missing is None)
    assert interact.call_count == (1 if missing is None else 0)
