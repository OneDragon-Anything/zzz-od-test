from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_storage import BagelDragController as BagelDragController
from test.harness.bagel_storage import WatchedCloseSearch as WatchedCloseSearch
from test.harness.bagel_storage import WatchedStore as WatchedStore
from test.harness.bagel_storage import _copy_item as _copy_item
from test.harness.bagel_storage import _fill_slots as _fill_slots
from test.harness.bagel_storage import _pending_store_frames as _pending_store_frames
from test.harness.bagel_storage import controller as controller
from test.harness.fixture_controller import (
    enter_running_state,
    reset_running_state,
)

from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_SWAP,
    BagelSlotMark,
    StoreChoice,
    choose_store_action,
    inspect_occupied,
)
from zzz_od.application.bagel.bagel_slots import (
    RESULT_SLOT_CENTERS,
    SAFE_SLOT_CENTERS,
)
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_store_ignores_currency_without_closing(
    test_context: TestContext,
    controller: BagelDragController,
) -> None:
    """金币结果不拖拽，留在搜索结果中，不关闭面板。"""
    root = next(
        path for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test'
    )
    currency_screen = cv2_utils.read_image(
        str(root / 'screens/贝果-局内/材料占箱待换贵重物品-20260921.webp'),
    )
    before = cv2_utils.read_image(
        str(root / 'screens/贝果-局内/武备箱已入箱-实机.webp'),
    )
    _copy_item(before, currency_screen, RESULT_SLOT_CENTERS[1], RESULT_SLOT_CENTERS[0])
    result_marks = inspect_occupied(before, RESULT_SLOT_CENTERS)
    assert len(result_marks) == 1
    assert result_marks[0].item_type == '金币'
    controller.set_phases([{'frame': before}])
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelStoreSafe.STATUS_DONE
        assert result.data['moved'] == 0
        assert controller.recorded_drags == []
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


def test_store_preserves_panel_until_explicit_close(
    test_context: TestContext,
    controller: BagelDragController,
) -> None:
    """正式收集参数完成实际拖拽后保留面板，由下一操作独立关闭。"""
    pending, mid, done = _pending_store_frames()
    controller.set_phases(
        [
            {'frame': pending, 'exit': ('on_drag',)},
            {'frame': mid, 'exit': ('on_drag',)},
            {'frame': done, 'exit': ('on_click_in', '贝果-局内', '搜查返回')},
            {'frame': ('贝果-局内', '高危A出生-原生1080')},
        ]
    )
    store = WatchedStore(test_context)
    close = WatchedCloseSearch(test_context)
    enter_running_state(test_context)
    try:
        result = store.execute()
        assert result.success and result.status == BagelStoreSafe.STATUS_DONE
        assert result.data['moved'] == 2
        assert controller.phase_idx == 2
        assert controller.recorded_clicks == []
        assert controller.recorded_drags == [
            (RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS[0]),
            (RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[1]),
        ]
        assert close.execute().success
        assert controller.phase_idx == 3
        assert len(controller.recorded_drags) == 2
    finally:
        reset_running_state(test_context, store)
        reset_running_state(test_context, close)


@pytest.mark.parametrize(
    'missed_drags',
    [
        3,
    ],
)
def test_store_second_drag_can_land(
    test_context: TestContext,
    controller: BagelDragController,
    missed_drags: int,
) -> None:
    """第一次拖完画面没变时，再拖一次可以把同一件拖进安全箱。"""
    pending, mid, done = _pending_store_frames()
    controller.set_phases(
        [
            *[{'frame': pending, 'exit': ('on_drag',)} for _ in range(missed_drags)],
            {'frame': pending, 'exit': ('on_drag',)},
            {'frame': mid, 'exit': ('on_drag',)},
            {'frame': done},
        ]
    )
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.data['moved'] == 2
        assert controller.recorded_drags[:2] == [
            (RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS[0]),
            (RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS[0]),
        ]
        assert len(controller.recorded_drags) == missed_drags + 2
        assert controller.recorded_drags[-1] == (
            RESULT_SLOT_CENTERS[0],
            SAFE_SLOT_CENTERS[1],
        )
    finally:
        reset_running_state(test_context, op)


def test_store_stops_when_item_leaves_grid_without_entering_safe(
    test_context: TestContext,
    controller: BagelDragController,
) -> None:
    """源格空了、安全箱目标格仍空，再看一帧后停止，不再拖。"""
    pending, _mid, _done = _pending_store_frames()
    vanished = pending.copy()
    empty = RESULT_SLOT_CENTERS[4]
    _copy_item(vanished, pending, empty, RESULT_SLOT_CENTERS[1])
    controller.set_phases(
        [
            {'frame': pending, 'exit': ('on_drag',)},
            {'frame': vanished},
        ]
    )
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert result.status == '离开了搜索格但没进安全箱，停止并保留现场'
        assert len(controller.recorded_drags) == 1
    finally:
        reset_running_state(test_context, op)


def test_better_material_can_replace_lower_quality_material_on_failed_live_frame() -> (
    None
):
    """截图中的拖拽虽失败，优先级仍允许 S 材料替换 A 材料。"""
    screen = cv2_utils.read_image(
        str(
            next(Path('zzz-od-test/screens').rglob('保险箱材料无效对换-20260924.webp'))
        ),
    )
    results = inspect_occupied(screen, RESULT_SLOT_CENTERS)
    safes = inspect_occupied(screen, SAFE_SLOT_CENTERS)
    assert results[1].index == 3 and results[1].item_type == '材料'
    assert safes[2].index == 2 and safes[2].item_type == '材料'
    choice = choose_store_action(results, safes, [])
    assert choice is not None and choice.kind == ACTION_SWAP
    assert (choice.source_index, choice.dest_index) == (3, 2)


def test_alternate_material_badge_cannot_replace_higher_quality_material() -> None:
    """历史 other 模板同为材料，不能把 A 材料当非材料去替换 S 材料。"""
    screen = cv2_utils.read_image(
        str(
            next(Path('zzz-od-test/screens').rglob('保险箱材料不可对换-20260924.webp'))
        ),
    )
    results = inspect_occupied(screen, RESULT_SLOT_CENTERS)
    safes = inspect_occupied(screen, SAFE_SLOT_CENTERS)
    assert results[1].index == 4 and results[1].item_type == '材料'
    assert results[1].quality == 'A'
    assert safes[2].index == 2 and safes[2].item_type == '材料'
    assert safes[2].quality == 'S'
    choice = choose_store_action(results, safes, [])
    assert choice is None


def test_store_stops_when_swapped_slot_has_different_item(
    test_context: TestContext,
    controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一结果格再次被选中对换时结束收集，不再拖第二次。"""
    op = BagelStoreSafe(test_context)
    op.last_screenshot = test_context.load_screen('贝果-局内', '武备箱待入箱-实机')
    mark = BagelSlotMark(4, RESULT_SLOT_CENTERS[4], 'S', '材料')
    choice = StoreChoice(ACTION_SWAP, 4, 4, mark)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op._panel_guard, 'observe', lambda *_: True)
    monkeypatch.setattr(op, '_search_complete', lambda: True)
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_store.inspect_occupied',
        lambda *_args: [mark],
    )
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_store.choose_store_action',
        lambda *_args: choice,
    )
    op._swap_seen.add(4)
    result = op.store_next()
    assert result.is_success
    assert result.status == BagelStoreSafe.STATUS_DONE
    assert controller.recorded_drags == []


def test_store_swaps_better_item_when_safe_full(
    test_context: TestContext,
    controller: BagelDragController,
) -> None:
    """箱满时，金棱镜应对换紫道具所在的最差安全箱格。"""
    pending = cv2_utils.read_image(
        str(next(Path('zzz-od-test/screens').rglob('武备箱待入箱-实机.webp'))),
    )
    full = pending.copy()
    _fill_slots(full, pending, RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS)
    _copy_item(full, pending, RESULT_SLOT_CENTERS[4], RESULT_SLOT_CENTERS[0])
    after = full.copy()
    _copy_item(after, full, RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS[0])
    _copy_item(after, full, SAFE_SLOT_CENTERS[0], RESULT_SLOT_CENTERS[1])
    controller.set_phases(
        [
            {'frame': full, 'exit': ('on_drag',)},
            {'frame': after},
        ]
    )
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelStoreSafe.STATUS_DONE
        assert result.data['moved'] == 0
        assert controller.recorded_drags == [
            (RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS[0]),
        ]
    finally:
        reset_running_state(test_context, op)


def test_store_leaves_low_priority_when_safe_full(
    test_context: TestContext,
    controller: BagelDragController,
) -> None:
    """安全箱已满时，低优先级材料留在搜索结果中，不再发送输入。"""
    pending = cv2_utils.read_image(
        str(next(Path('zzz-od-test/screens').rglob('武备箱待入箱-实机.webp'))),
    )
    material_screen = cv2_utils.read_image(
        str(
            next(
                Path('zzz-od-test/screens').rglob('材料占箱待换贵重物品-20260921.webp')
            )
        ),
    )
    blocked = pending.copy()
    _fill_slots(blocked, pending, RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS)
    _copy_item(blocked, material_screen, SAFE_SLOT_CENTERS[3], RESULT_SLOT_CENTERS[0])
    _copy_item(blocked, material_screen, SAFE_SLOT_CENTERS[4], RESULT_SLOT_CENTERS[1])
    result_marks = inspect_occupied(blocked, RESULT_SLOT_CENTERS)
    assert [mark.item_type for mark in result_marks] == ['材料', '材料']
    controller.set_phases([{'frame': blocked}])
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelStoreSafe.STATUS_DONE
        assert result.data['moved'] == 0
        assert controller.recorded_drags == []
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)
