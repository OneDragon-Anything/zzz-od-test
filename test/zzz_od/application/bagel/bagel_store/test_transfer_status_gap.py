"""搜查物品拖拽核对中，短暂漏识别不能丢失待核对数据。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import numpy as np
import pytest

from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


pytestmark = pytest.mark.usefixtures('no_round_wait')


def test_transfer_waits_for_status_then_checks_original_frames(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """物品已转移、状态文字短暂漏识别时，不重拖，恢复后核对原始基线。"""
    op = BagelStoreSafe(test_context)
    before = test_context.load_screen('贝果-局内', '武备箱待入箱-实机')
    after = test_context.load_screen('贝果-局内', '武备箱入箱中-实机')
    source, destination = RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[0]
    op._pending_before = before
    op._pending_source = source
    op._pending_destination = destination
    op._pending_kind = 'fill'
    op.last_screenshot = after
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_has_search_title', lambda: True)
    monkeypatch.setattr(op, '_search_ready', lambda: False)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    for _ in range(5):
        result = op.confirm_transfer()
        assert not result.is_fail
        assert op._pending_before is before
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op._panel_guard, 'observe', lambda *_: True)
    assert op.confirm_transfer().status == '继续装入'
    assert op.moved == 1
    assert op._pending_before is None
    drag.assert_not_called()


def test_transfer_stops_after_persistent_status_loss(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """等待有上限；持续漏识别后停止，不重复拖拽。"""
    op = BagelStoreSafe(test_context)
    op._pending_before = np.zeros((1080, 1920, 3), dtype=np.uint8)
    op._pending_source = RESULT_SLOT_CENTERS[0]
    op._pending_destination = SAFE_SLOT_CENTERS[0]
    op._pending_kind = 'fill'
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_has_search_title', lambda: True)
    monkeypatch.setattr(op, '_search_ready', lambda: False)
    for _ in range(5):
        assert not op.confirm_transfer().is_fail
    assert op.confirm_transfer().is_fail
    assert op._pending_before is None
