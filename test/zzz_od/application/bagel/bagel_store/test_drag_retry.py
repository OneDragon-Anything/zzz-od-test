from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import numpy as np
import pytest

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('source_now,dest_now', [(False, True), (True, True), (False, False)])
def test_fill_checks_target_before_counting_success(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    source_now: bool, dest_now: bool,
) -> None:
    """目标确实变为占用才记成功；源目标都空先复查，不误记已入箱。"""
    op = BagelStoreSafe(test_context)
    before = np.zeros((1, 1, 3), dtype=np.uint8)
    after = before.copy()
    source, target = RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[0]
    op._pending_before, op.last_screenshot = before, after
    op._pending_source, op._pending_destination, op._pending_kind = source, target, 'fill'
    monkeypatch.setattr(op, '_check_search_panel', lambda: None)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_safe_slots',
                        lambda _: SimpleNamespace(locked=[]))
    monkeypatch.setattr(op, '_drag_visually_ok', lambda *_: False)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.slot_occupied',
                        lambda screen, center: (center == source) if screen is before
                        else (source_now if center == source else dest_now))
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    result = op.confirm_transfer()
    if dest_now:
        assert result.is_success and op.moved == 1
    else:
        assert result.result == OperationRoundResultEnum.WAIT and op.moved == 0
        assert op.confirm_transfer().is_fail
    drag.assert_not_called()


@pytest.mark.parametrize('kind,budget', [('fill', 3), ('swap', 1)])
def test_retry_budget_keeps_the_same_destination(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, kind: str, budget: int,
) -> None:
    """填空额外三次、对换额外一次，超限停止且不改变目标格。"""
    op = BagelStoreSafe(test_context)
    op._pending_before = np.zeros((1, 1, 3), dtype=np.uint8)
    op.last_screenshot = op._pending_before.copy()
    source, target = RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[0]
    op._pending_source, op._pending_destination, op._pending_kind = source, target, kind
    monkeypatch.setattr(op, '_check_search_panel', lambda: None)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_safe_slots',
                        lambda _: SimpleNamespace(locked=[]))
    monkeypatch.setattr(op, '_drag_visually_ok', lambda *_: False)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.slot_occupied',
                        lambda _, center: kind == 'swap' or center == source)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    for _ in range(budget):
        assert op.confirm_transfer().result == OperationRoundResultEnum.WAIT
    assert op.confirm_transfer().is_fail
    assert drag.call_count == budget
    assert all(call.args == (source, target) for call in drag.call_args_list)
    assert op.moved == 0
