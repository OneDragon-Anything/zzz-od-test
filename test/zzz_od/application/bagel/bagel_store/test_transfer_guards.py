from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import numpy as np
import pytest
from test.harness.bagel_loadout import running_operation
from test.harness.bagel_safe_slots import (
    copy_safe_slot,
    lock_safe_suffix,
    native_four_slot_screen,
)
from test.harness.bagel_store_frames import SafeDragController as SafeDragController
from test.harness.bagel_store_frames import WatchedSafeStore as WatchedSafeStore
from test.harness.bagel_store_frames import copy_result_item as copy_result_item

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('kind,budget', [('fill', 3), ('swap', 1)])
def test_retry_budget_keeps_the_same_destination(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    budget: int,
) -> None:
    """填空额外三次、对换额外一次，超限停止且不改变目标格。"""
    op = BagelStoreSafe(test_context)
    op._pending_before = np.zeros((1, 1, 3), dtype=np.uint8)
    op.last_screenshot = op._pending_before.copy()
    source, target = RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[0]
    op._pending_source, op._pending_destination, op._pending_kind = source, target, kind
    monkeypatch.setattr(op, '_check_search_panel', lambda: None)
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_store.inspect_safe_slots',
        lambda _: SimpleNamespace(locked=[]),
    )
    monkeypatch.setattr(op, '_drag_visually_ok', lambda *_: False)
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_store.slot_occupied',
        lambda _, center: kind == 'swap' or center == source,
    )
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    for _ in range(budget):
        assert op.confirm_transfer().result == OperationRoundResultEnum.WAIT
    assert op.confirm_transfer().is_fail
    assert drag.call_count == budget
    assert all(call.args == (source, target) for call in drag.call_args_list)
    assert op.moved == 0


@pytest.mark.parametrize(
    'capacity,swap',
    [
        (4, True),
    ],
)
def test_store_fills_or_swaps_only_unlocked_slots(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    no_round_wait: None,
    capacity: int,
    swap: bool,
) -> None:
    """实拍像素合成容量场景，完整执行最后一格入箱或满箱对换及回读。"""
    pending = test_context.load_screen('贝果-局内', '武备箱待入箱-实机')
    native = native_four_slot_screen()
    before = pending.copy()
    # 清空结果，用同一件 S 贵重物品占两个结果格；第二件应因满箱且无升级而留下。
    for center in RESULT_SLOT_CENTERS[:5]:
        copy_result_item(before, pending, RESULT_SLOT_CENTERS[4], center)
    for center in SAFE_SLOT_CENTERS[: capacity - 1]:
        copy_safe_slot(before, native, SAFE_SLOT_CENTERS[0], center)
    if swap:
        copy_safe_slot(
            before, pending, RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[capacity - 1]
        )
    for center in RESULT_SLOT_CENTERS[:2]:
        copy_result_item(before, native, SAFE_SLOT_CENTERS[0], center)
    before = lock_safe_suffix(before, capacity)
    after = before.copy()
    if swap:
        copy_result_item(after, pending, RESULT_SLOT_CENTERS[0], RESULT_SLOT_CENTERS[0])
    else:
        copy_result_item(after, pending, RESULT_SLOT_CENTERS[4], RESULT_SLOT_CENTERS[0])
    copy_safe_slot(after, native, SAFE_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[capacity - 1])
    controller = SafeDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': before, 'exit': ('on_drag',)}, {'frame': after}])
    op = WatchedSafeStore(test_context)
    with running_operation(op):
        result = op.execute()
    assert result.success, result.status
    assert result.status == op.STATUS_DONE
    assert result.data['moved'] == (0 if swap else 1)
    assert [point.tuple() for point in controller.drags] == [
        SAFE_SLOT_CENTERS[capacity - 1].tuple()
    ]
    assert controller.recorded_clicks == []
