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
from test.harness.bagel_store_frames import (
    SafeDragController,
    WatchedSafeStore,
    copy_result_item,
)

from zzz_od.application.bagel.bagel_search_panel import (
    SearchPanelGuard,
)
from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from test.conftest import TestContext

ARCHIVE = Path(__file__).resolve().parents[5] / 'screens/贝果-局内/搜查面板过渡'

ANOMALIES = json.loads((ARCHIVE / '识别记录.json').read_text('utf-8'))[
    'ready_anomalies'
]

pytestmark = pytest.mark.usefixtures('no_round_wait')


def frame(index: int) -> MatLike:
    """读取原始像素无损归档，文件名中的帧号对应素材索引。"""
    return np.array(Image.open(ARCHIVE / f'帧{index:04d}.webp').convert('RGB'))


@pytest.mark.parametrize('after_drag', [False, True])
def test_transition_then_hud_interrupts_execute(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    after_drag: bool,
) -> None:
    """在收集或拖后回读遇到关闭过程，完整流程退出且不补拖、不按F。"""
    controller = SafeDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    phases = []
    if after_drag:
        phases.append(
            {
                'frame': test_context.load_screen('贝果-局内', '武备箱待入箱-实机'),
                'exit': ('on_drag',),
            }
        )
    phases.extend(
        [
            {'frame': frame(206), 'exit': ('on_polls', 1)},
            {'frame': frame(222)},
        ]
    )
    controller.set_phases(phases)
    op = WatchedSafeStore(test_context)
    with running_operation(op):
        result = op.execute()
    assert not result.success and result.status == op.STATUS_INTERRUPTED
    assert len(controller.drags) == int(after_drag)
    assert controller.recorded_clicks == [] and controller.recorded_inputs == []
    assert op._pending_before is None


def test_transfer_wait_keeps_original_move_until_stable(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
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
    controller.set_phases(
        [
            {'frame': pending, 'exit': ('on_drag',)},
            {'frame': frame(1105), 'exit': ('on_polls', 1)},
            {'frame': after},
        ]
    )
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


def test_persistent_transition_stops_with_saved_scene(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
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
    assert (
        not result.success and result.status == '搜查面板状态持续不明，停止并保留现场'
    )
    assert op._panel_wait_rounds == 6
    assert controller.drags == []
    saved.assert_called_once()


@pytest.mark.parametrize('index', [row['frame'] for row in ANOMALIES])
def test_all_recorded_anomalies_fail_stability(index: int) -> None:
    """全部异常帧连续出现也不得被稳定守卫接受。"""
    guard = SearchPanelGuard()
    assert not guard.observe(frame(200), 1)
    assert not guard.observe(frame(index), 2)
    assert not guard.observe(frame(index), 3)
