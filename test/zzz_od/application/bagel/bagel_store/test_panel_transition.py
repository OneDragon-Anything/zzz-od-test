"""真实开关过渡进入收集和回读节点时，不能发送物品输入。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image
from test.harness.bagel_loadout import running_operation
from test.zzz_od.application.bagel.bagel_store.test_execute_capacity import (
    SafeDragController,
    WatchedSafeStore,
    copy_result_item,
)

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_search_panel import (
    SearchPanelGuard,
    search_panel_pixels,
)
from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from test.conftest import TestContext


ARCHIVE = Path(__file__).resolve().parents[5] / 'screens/贝果-局内/搜查面板过渡'
ANOMALIES = json.loads((ARCHIVE / '识别记录.json').read_text('utf-8'))['ready_anomalies']
pytestmark = pytest.mark.usefixtures('no_round_wait')


def frame(index: int) -> MatLike:
    """读取原始像素无损归档，文件名中的帧号对应素材索引。"""
    return np.array(Image.open(ARCHIVE / f'帧{index:04d}.webp').convert('RGB'))


@pytest.mark.parametrize('index', [row['frame'] for row in ANOMALIES])
@pytest.mark.parametrize('phase', ['store', 'transfer'])
def test_transition_never_reaches_item_decision(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, index: int, phase: str,
) -> None:
    """文字门槛通过的全部28张异常实拍，均不得进入格子决策或重拖。"""
    op = BagelStoreSafe(test_context)
    before = frame(200)
    assert not op._panel_guard.observe(before, 1.0)
    op.last_screenshot = frame(index)
    op.last_screenshot_time = 2.0
    op._pending_before = before
    op._pending_source = RESULT_SLOT_CENTERS[0]
    op._pending_destination = SAFE_SLOT_CENTERS[0]
    op._pending_kind = 'fill'
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    inspect = MagicMock(side_effect=AssertionError('过渡画面不应进入格子识别'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_safe_slots', inspect)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_occupied', inspect)
    result = op.store_next() if phase == 'store' else op.confirm_transfer()
    assert result.result == OperationRoundResultEnum.WAIT
    assert op._pending_before is before
    inspect.assert_not_called()
    drag.assert_not_called()


@pytest.mark.parametrize('after_drag', [False, True])
def test_transition_then_hud_interrupts_execute(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, after_drag: bool,
) -> None:
    """在收集或拖后回读遇到关闭过程，完整流程退出且不补拖、不按F。"""
    controller = SafeDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    phases = []
    if after_drag:
        phases.append({'frame': test_context.load_screen('贝果-局内', '武备箱待入箱-实机'),
                       'exit': ('on_drag',)})
    phases.extend([
        {'frame': frame(206), 'exit': ('on_polls', 1)},
        {'frame': frame(222)},
    ])
    controller.set_phases(phases)
    op = WatchedSafeStore(test_context)
    with running_operation(op):
        result = op.execute()
    assert not result.success and result.status == op.STATUS_INTERRUPTED
    assert len(controller.drags) == int(after_drag)
    assert controller.recorded_clicks == [] and controller.recorded_inputs == []
    assert op._pending_before is None


def test_transfer_wait_keeps_original_move_until_stable(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """合成单件搬运与短暂偏移序列，恢复后核验同一次搬运，不因等待重拖。"""
    pending = test_context.load_screen('贝果-局内', '武备箱待入箱-实机').copy()
    empty = RESULT_SLOT_CENTERS[4]
    copy_result_item(pending, pending.copy(), empty, RESULT_SLOT_CENTERS[0])
    after = pending.copy()
    copy_result_item(after, pending, RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS[0])
    copy_result_item(after, pending, empty, RESULT_SLOT_CENTERS[1])
    controller = SafeDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([
        {'frame': pending, 'exit': ('on_drag',)},
        {'frame': frame(1105), 'exit': ('on_polls', 1)},
        {'frame': after},
    ])
    op = WatchedSafeStore(test_context)
    with running_operation(op):
        result = op.execute()
    assert result.success and result.data['moved'] == 1
    assert controller.drags == [SAFE_SLOT_CENTERS[0]]
    assert controller.recorded_clicks == [] and controller.recorded_inputs == []


def test_shifted_static_frames_are_not_accepted() -> None:
    """重复同一张偏移画面也不能被两帧稳定条件放行。"""
    guard = SearchPanelGuard()
    assert not guard.observe(frame(1105), 1)
    assert not guard.observe(frame(1105), 2)
    assert not guard.observe(frame(200), 3)
    assert not guard.observe(frame(200), 3)
    assert guard.observe(frame(200), 4)


@pytest.mark.parametrize('phase', ['store', 'transfer'])
def test_closed_panel_reports_interruption_without_f_prompt(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    """不要求箱子提示或F图标；已回局内就报告中断且不重开。"""
    op = BagelStoreSafe(test_context)
    op.last_screenshot = frame(222)
    op._pending_before = frame(200)
    op._pending_source = RESULT_SLOT_CENTERS[0]
    op._pending_destination = SAFE_SLOT_CENTERS[0]
    op._pending_kind = 'fill'
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: False)
    monkeypatch.setattr(op, '_has_search_title', lambda: False)
    monkeypatch.setattr(op, 'round_by_find_area', lambda _s, _n, area:
                        op.round_success() if area == '按键-普通攻击' else op.round_retry())
    result = op.store_next() if phase == 'store' else op.confirm_transfer()
    assert result.is_fail and result.status == op.STATUS_INTERRUPTED
    assert op._pending_before is None


def test_opening_then_stable_empty_finishes_without_input(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重新打开过渡结束后，完整节点等待两张稳定图再认定没有可搬物品。"""
    controller = SafeDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([
        {'frame': frame(1103), 'exit': ('on_polls', 1)},
        {'frame': frame(1105), 'exit': ('on_polls', 1)},
        {'frame': frame(1114)},
    ])
    op = WatchedSafeStore(test_context)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_occupied', lambda *_: [])
    with running_operation(op):
        result = op.execute()
    assert result.success and result.status == op.STATUS_EMPTY
    assert controller.drags == [] and controller.recorded_clicks == []


def test_persistent_transition_stops_with_saved_scene(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """面板持续偏移时等待有界，不能依靠Operation总超时脱身。"""
    controller = SafeDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': frame(1105)}])
    op = WatchedSafeStore(test_context)
    saved = MagicMock()
    monkeypatch.setattr(op, 'save_screenshot', saved)
    with running_operation(op):
        result = op.execute()
    assert not result.success and result.status == '搜查面板状态持续不明，停止并保留现场'
    assert op._panel_wait_rounds == 6
    assert controller.drags == []
    saved.assert_called_once()


@pytest.mark.parametrize('state', ['武备箱待入箱-实机', '武备箱入箱中-实机', '武备箱已入箱-实机',
                                  '四格安全箱部分占用-20261004', '电子保险箱搜索完成'])
def test_normal_archived_panels_keep_supported_layout(test_context: TestContext, state: str) -> None:
    """空箱、占用、锁定和不同容器标题均能确认原有位置。"""
    assert search_panel_pixels(test_context.load_screen('贝果-局内', state)) is not None
