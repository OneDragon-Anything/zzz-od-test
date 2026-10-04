from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_safe_slots import native_four_slot_screen

from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('locked', [False, True])
def test_transfer_never_retries_into_unknown_or_locked_slot(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, locked: bool,
) -> None:
    """回读发现目标锁定或安全箱未知时，不补拖，也不记为搬运成功。"""
    op = BagelStoreSafe(test_context)
    op._pending_before = test_context.load_screen('贝果-局内', '武备箱待入箱-实机')
    op._pending_source = RESULT_SLOT_CENTERS[0]
    op._pending_destination = SAFE_SLOT_CENTERS[4 if locked else 1]
    op._pending_kind = 'fill'
    op.last_screenshot = native_four_slot_screen()
    if not locked:
        op.last_screenshot[851:947, 312:408] = 0
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    result = op.confirm_transfer()
    assert result.is_fail and '状态不明或目标已锁定' in result.status
    assert op.moved == 0 and not op.acted
    assert op._pending_before is None
    drag.assert_not_called()
