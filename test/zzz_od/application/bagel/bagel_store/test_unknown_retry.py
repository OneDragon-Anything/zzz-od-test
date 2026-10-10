from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_loadout import TransferController, running_operation
from test.harness.fixture_controller import WatchdogOperationMixin

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


pytestmark = pytest.mark.usefixtures('no_round_wait')


class WatchedStore(WatchdogOperationMixin, BagelStoreSafe):
    """完整节点执行必须在有限轮数内恢复或停止。"""

    watchdog_max_rounds: int = 12


@pytest.mark.parametrize('persistent', [False, True])
def test_unknown_frames_execute_with_bounded_wait(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, persistent: bool,
) -> None:
    """正常面板单格内容被遮挡时有界重读；清晰后继续，不触发拖拽。"""
    controller = TransferController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    clear = test_context.load_screen('贝果-局内', '搜查面板过渡/帧1114')
    occluded = clear.copy()
    c = SAFE_SLOT_CENTERS[0]
    occluded[c.y-32:c.y+32, c.x-32:c.x+32] = 0
    phases = [{'frame': occluded}]
    if not persistent:
        phases[0]['exit'] = ('on_polls', 3)
        phases.append({'frame': clear})
    controller.set_phases(phases)
    op = WatchedStore(test_context)
    # 不搬运录像右侧的物资；保留真实面板 OCR、格子识别、节点等待及截图推进。
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_occupied', lambda *_: [])
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    saved = MagicMock()
    monkeypatch.setattr(op, 'save_screenshot', saved)
    with running_operation(op):
        result = op.execute()
    assert result.success is not persistent
    if persistent:
        assert result.status == '安全箱格子状态不明，停止并保留现场'
        assert op._safe_unknown_rounds == 4
        saved.assert_called_once()
    else:
        assert result.status == op.STATUS_EMPTY
        assert op._safe_unknown_rounds == 0
    drag.assert_not_called()


def test_transfer_unknown_keeps_baseline_until_known(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拖拽后暂时遮挡，恢复时核对同次搬运，不追加拖拽。"""
    op = BagelStoreSafe(test_context)
    before = test_context.load_screen('贝果-局内', '武备箱待入箱-实机')
    after = test_context.load_screen('贝果-局内', '武备箱入箱中-实机')
    op._pending_before = before
    op._pending_source = RESULT_SLOT_CENTERS[0]
    op._pending_destination = SAFE_SLOT_CENTERS[0]
    op._pending_kind = 'fill'
    op.last_screenshot = after.copy()
    c = SAFE_SLOT_CENTERS[1]
    op.last_screenshot[c.y-48:c.y+48, c.x-48:c.x+48] = 0
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op._panel_guard, 'observe', lambda *_: True)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    for _ in range(3):
        assert op.confirm_transfer().result == OperationRoundResultEnum.WAIT
        assert op._pending_before is before and op.moved == 0
    op.last_screenshot = after
    assert op.confirm_transfer().status == '继续装入'
    assert op.moved == 1 and op._safe_unknown_rounds == 0
    drag.assert_not_called()
