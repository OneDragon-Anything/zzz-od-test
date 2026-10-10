from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_close_search import BagelCloseSearch
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_SWAP,
    BagelSlotMark,
    StoreChoice,
    choose_store_action,
    inspect_occupied,
)
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse
from zzz_od.application.bagel.bagel_slots import (
    RESULT_SLOT_CENTERS,
    SAFE_SLOT_CENTERS,
    slot_crop,
)
from zzz_od.application.bagel.bagel_store import BagelStoreSafe
from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from test.conftest import TestContext


class BagelDragController(FixtureController):
    """记录拖拽，并支持 on_drag 推进剧本。"""

    def __init__(self, ctx: TestContext) -> None:
        super().__init__(ctx)
        self.recorded_drags: list[tuple[Point | None, Point]] = []

    def set_phases(self, phases: list[dict]) -> None:
        """重置拖拽记录。"""
        super().set_phases(phases)
        self.recorded_drags.clear()

    def drag_to(
        self,
        end: Point,
        start: Point | None = None,
        duration: float = 0.5,
        press_time: float = 0,
    ) -> None:
        """记录拖拽；exit 为 on_drag / on_action 时推进画面。"""
        # 首次入箱、满箱对换和失败重拖均须先按住，避免拖成滚动列表。
        assert press_time == 0.1
        assert duration == 0.8
        self.recorded_drags.append((start, end))
        exit_spec = self._current_exit()
        if exit_spec is not None and exit_spec[0] in ('on_drag', 'on_action'):
            self._advance_phase()

    @property
    def current_frame(self) -> MatLike:
        """允许剧本直接塞合成帧，不必先写入截图存档。"""
        frame = self._phases[self._phase_idx]['frame']
        if isinstance(frame, tuple):
            screen_name, state = frame
            return self.ctx.load_screen(screen_name, state)
        return frame


class WatchedStore(WatchdogOperationMixin, BagelStoreSafe):
    """限制入箱轮数。"""

    watchdog_max_rounds: int = 40


def _copy_item(
    destination: MatLike, source: MatLike, src_center: Point, dst_center: Point,
) -> None:
    """把源格占用裁剪和左上角标窗贴到目标格，避免合成帧类型错位。"""
    patch = slot_crop(source, src_center, half=40)
    if patch is None:
        raise AssertionError('缺少格子裁剪')
    half = patch.shape[0] // 2
    x1 = int(dst_center.x) - half
    y1 = int(dst_center.y) - half
    destination[y1:y1 + patch.shape[0], x1:x1 + patch.shape[1]] = patch
    badge = 40
    offset = 52
    sx1 = int(src_center.x) - offset
    sy1 = int(src_center.y) - offset
    dx1 = int(dst_center.x) - offset
    dy1 = int(dst_center.y) - offset
    destination[dy1:dy1 + badge, dx1:dx1 + badge] = source[sy1:sy1 + badge, sx1:sx1 + badge]


def _pending_store_frames() -> tuple[MatLike, MatLike, MatLike]:
    """按品质优先合成：先入金棱镜再入紫道具。"""
    pending = cv2_utils.read_image(
        str(next(Path('zzz-od-test/screens').rglob('武备箱待入箱-实机.webp'))),
    )
    empty = RESULT_SLOT_CENTERS[4]
    mid = pending.copy()
    _copy_item(mid, pending, RESULT_SLOT_CENTERS[1], SAFE_SLOT_CENTERS[0])
    _copy_item(mid, pending, empty, RESULT_SLOT_CENTERS[1])
    done = mid.copy()
    _copy_item(done, pending, RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[1])
    _copy_item(done, pending, empty, RESULT_SLOT_CENTERS[0])
    return pending, mid, done


def test_store_ignores_currency_without_closing(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """金币结果不拖拽，留在搜索结果中，不关闭面板。"""
    root = next(path for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')
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


class WatchedDeposit(WatchdogOperationMixin, BagelDeposit):
    """限制入仓轮数。"""

    watchdog_max_rounds: int = 25


class WatchedApp(WatchdogOperationMixin, BagelApp):
    """限制单局编排轮数。"""

    watchdog_max_rounds: int = 40


@pytest.fixture
def controller(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> BagelDragController:
    """使用真截图与 OCR，替换输入并允许拖拽推进。"""
    result = BagelDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', result)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    return result


class WatchedCloseSearch(WatchdogOperationMixin, BagelCloseSearch):
    """独立关闭流程使用有界看门狗。"""

    watchdog_max_rounds: int = 20


def test_store_preserves_panel_until_explicit_close(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """正式收集参数完成实际拖拽后保留面板，由下一操作独立关闭。"""
    pending, mid, done = _pending_store_frames()
    controller.set_phases([
        {'frame': pending, 'exit': ('on_drag',)},
        {'frame': mid, 'exit': ('on_drag',)},
        {'frame': done, 'exit': ('on_click_in', '贝果-局内', '搜查返回')},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ])
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


def test_close_waits_and_retries_before_confirming_hud(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """搜查中等待，首次关闭未生效时再次关闭，看到 HUD 才结束。"""
    controller.set_phases([
        {'frame': ('贝果-局内', '武备箱搜查中-r07'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '武备箱已入箱-实机'),
         'exit': ('on_click_in', '贝果-局内', '搜查返回')},
        {'frame': ('贝果-局内', '武备箱已入箱-实机'),
         'exit': ('on_click_in', '贝果-局内', '搜查返回')},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ])
    op = WatchedCloseSearch(test_context)
    enter_running_state(test_context)
    try:
        assert op.execute().success
        assert controller.phase_idx == 3
        assert len(controller.recorded_clicks) == 2
        assert controller.recorded_drags == []
        assert controller.recorded_inputs == []
    finally:
        reset_running_state(test_context, op)


def test_store_empty_result_preserves_panel_without_drag(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """结果格已空时不拖拽，也不关闭面板。"""
    controller.set_phases([{'frame': ('贝果-局内', '武备箱已入箱-实机')}])
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelStoreSafe.STATUS_EMPTY
        assert result.data['moved'] == 0
        assert controller.recorded_drags == []
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


def test_store_stops_when_drag_has_no_effect(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """填空最多首次加三次重拖，仍不变就停，不继续盲拖。"""
    controller.set_phases([
        {'frame': ('贝果-局内', '武备箱待入箱-实机'), 'exit': ('on_drag',)},
        {'frame': ('贝果-局内', '武备箱待入箱-实机')},
    ])
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '无变化' in result.status
        assert len(controller.recorded_drags) == 4
        assert all(drag == controller.recorded_drags[0] for drag in controller.recorded_drags)
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('missed_drags', [1, 3])
def test_store_second_drag_can_land(
    test_context: TestContext, controller: BagelDragController, missed_drags: int,
) -> None:
    """第一次拖完画面没变时，再拖一次可以把同一件拖进安全箱。"""
    pending, mid, done = _pending_store_frames()
    controller.set_phases([
        *[{'frame': pending, 'exit': ('on_drag',)} for _ in range(missed_drags)],
        {'frame': pending, 'exit': ('on_drag',)},
        {'frame': mid, 'exit': ('on_drag',)},
        {'frame': done},
    ])
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
        assert controller.recorded_drags[-1] == (RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[1])
    finally:
        reset_running_state(test_context, op)


def test_store_stops_when_item_leaves_grid_without_entering_safe(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """源格空了、安全箱目标格仍空，再看一帧后停止，不再拖。"""
    pending, _mid, _done = _pending_store_frames()
    vanished = pending.copy()
    empty = RESULT_SLOT_CENTERS[4]
    _copy_item(vanished, pending, empty, RESULT_SLOT_CENTERS[1])
    controller.set_phases([
        {'frame': pending, 'exit': ('on_drag',)},
        {'frame': vanished},
    ])
    op = WatchedStore(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert result.status == '离开了搜索格但没进安全箱，停止并保留现场'
        assert len(controller.recorded_drags) == 1
    finally:
        reset_running_state(test_context, op)


def test_better_material_can_replace_lower_quality_material_on_failed_live_frame() -> None:
    """截图中的拖拽虽失败，优先级仍允许 S 材料替换 A 材料。"""
    screen = cv2_utils.read_image(
        str(next(Path('zzz-od-test/screens').rglob('保险箱材料无效对换-20260924.webp'))),
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
        str(next(Path('zzz-od-test/screens').rglob('保险箱材料不可对换-20260924.webp'))),
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
    test_context: TestContext, controller: BagelDragController, monkeypatch: pytest.MonkeyPatch,
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
        'zzz_od.application.bagel.bagel_store.inspect_occupied', lambda *_args: [mark],
    )
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_store.choose_store_action', lambda *_args: choice,
    )
    op._swap_seen.add(4)
    result = op.store_next()
    assert result.is_success
    assert result.status == BagelStoreSafe.STATUS_DONE
    assert controller.recorded_drags == []


def _fill_slots(destination: MatLike, source: MatLike, src_center: Point, centers: tuple[Point, ...]) -> None:
    """把同一件物品贴满一组格子。"""
    for center in centers:
        _copy_item(destination, source, src_center, center)


def test_store_swaps_better_item_when_safe_full(
    test_context: TestContext, controller: BagelDragController,
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
    controller.set_phases([
        {'frame': full, 'exit': ('on_drag',)},
        {'frame': after},
    ])
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
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """安全箱已满时，低优先级材料留在搜索结果中，不再发送输入。"""
    pending = cv2_utils.read_image(
        str(next(Path('zzz-od-test/screens').rglob('武备箱待入箱-实机.webp'))),
    )
    material_screen = cv2_utils.read_image(
        str(next(Path('zzz-od-test/screens').rglob('材料占箱待换贵重物品-20260921.webp'))),
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


@pytest.mark.parametrize('before_frame,after_frame,before_count,after_count,safe_slots', [
    ('带物资仓库-r07-117s', '入仓后安全箱空-r07-118s', 259, 262, 5),
    ('成功闭环入仓前-4K缩放', '成功闭环入仓后-4K缩放', 243, 244, 2),
])
def test_deposit_clears_safe_with_warehouse_increase(
    test_context: TestContext, controller: BagelDragController,
    before_frame: str, after_frame: str, before_count: int, after_count: int, safe_slots: int,
) -> None:
    """真实入仓画面验证清空，仓库增量可小于安全箱占用。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', before_frame),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', after_frame)},
    ])
    op = WatchedDeposit(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelDeposit.STATUS_DONE
        assert result.data['warehouse_before'] == before_count
        assert result.data['warehouse_after'] == after_count
        assert result.data['moved'] == safe_slots
        assert controller.click_hit_area('贝果-仓库', '放入仓库')
    finally:
        reset_running_state(test_context, op)


def test_deposit_empty_safe_skips_click(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """安全箱已空时不点击放入仓库。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '入仓后安全箱空-实机')},
    ])
    op = WatchedDeposit(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelDeposit.STATUS_EMPTY
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('after,success', [(259, True), (258, False), (None, False)])
def test_deposit_stacked_items_and_invalid_counts(
    test_context: TestContext, controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch, after: int | None, success: bool,
) -> None:
    """模拟合并堆叠后格数不变；下降或读数缺失仍拒绝，截图保留真实清空过程。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '入仓后安全箱空-r07-118s')},
    ])
    op = WatchedDeposit(test_context)
    counts = iter([259, after])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success is success, result.status
        assert controller.click_hit_area('贝果-仓库', '放入仓库')
        if success:
            assert result.status == BagelDeposit.STATUS_DONE
            assert result.data['warehouse_after'] == result.data['warehouse_before']
            assert result.data['moved'] == 5  # 入仓前的安全箱格数，不是物品件数。
    finally:
        reset_running_state(test_context, op)


def test_deposit_rejects_click_without_clear(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """再点几次安全箱仍占用，不能记成功。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s')},
    ])
    op = WatchedDeposit(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '安全箱仍有' in result.status
        assert _clicks_in_area(test_context, controller, '放入仓库') >= 2
    finally:
        reset_running_state(test_context, op)


def test_deposit_second_click_clears_safe(
    test_context: TestContext, controller: BagelDragController,
) -> None:
    """第一次放入仓库没清空时，再点一次可以入仓。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '入仓后安全箱空-r07-118s')},
    ])
    op = WatchedDeposit(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelDeposit.STATUS_DONE
        assert _clicks_in_area(test_context, controller, '放入仓库') == 2
    finally:
        reset_running_state(test_context, op)


def _clicks_in_area(test_context: TestContext, controller: BagelDragController, area_name: str) -> int:
    """统计落在仓库文字区内的点击次数。"""
    rect = test_context.screen_loader.get_area('贝果-仓库', area_name).pc_rect
    return sum(
        1 for point in controller.recorded_clicks
        if rect.x1 <= point.x <= rect.x2 and rect.y1 <= point.y <= rect.y2
    )


def test_deposit_full_when_safe_stays_and_capacity_used_up(
    test_context: TestContext, controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """安全箱仍占用且全部格子已满时，记仓满成功而不是入仓成功。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s')},
    ])
    op = WatchedDeposit(test_context)
    monkeypatch.setattr(op, '_warehouse_pair', lambda: (280, 280))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelDeposit.STATUS_FULL
        assert result.data['safe_count'] == 5
        assert controller.click_hit_area('贝果-仓库', '放入仓库')
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('used', [279, 280], ids=['has_space', 'full'])
def test_partial_deposit_stops_without_second_click(
    test_context: TestContext, controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch, used: int,
) -> None:
    """满仓或未满仓都不能接受部分入仓，也不能再点一次。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s')},
    ])
    op = WatchedDeposit(test_context)
    monkeypatch.setattr(op, '_warehouse_pair', lambda: (used, 280))
    counts = iter([5, 4])
    monkeypatch.setattr(op, '_safe_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '部分入仓' in result.status
        assert _clicks_in_area(test_context, controller, '放入仓库') == 1
    finally:
        reset_running_state(test_context, op)


def test_full_capacity_and_empty_safe_without_growth_is_unproven(
    test_context: TestContext, controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """满仓点击后箱空而占用没变，不靠堆叠推测计成功。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '入仓后安全箱空-r07-118s')},
    ])
    op = WatchedDeposit(test_context)
    monkeypatch.setattr(op, '_warehouse_pair', lambda: (280, 280))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '不能证明物资已入仓' in result.status
        assert _clicks_in_area(test_context, controller, '放入仓库') == 1
    finally:
        reset_running_state(test_context, op)


@pytest.fixture
def app_setup(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> tuple[BagelConfig, BagelRunRecord, list[str]]:
    """注入默认出生画面和子操作替身，验证正式任务的编排顺序。"""
    controller = FixtureController(test_context)
    controller.set_phases([{'frame': ('贝果-局内', '高危A出生-原生1080')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelRunFlow.precondition', lambda *_: None)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_app.release_flow_inputs', lambda _: None)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.release_flow_inputs', lambda _: None)
    config = BagelConfig(99, 'standalone')
    config.max_success_rounds = 1
    record = BagelRunRecord(99)
    events: list[str] = []

    def ok(name: str, status: str = '') -> OperationResult:
        events.append(name)
        return OperationResult(True, status)

    monkeypatch.setattr(BagelEnter, 'execute', lambda self: ok('enter'))
    monkeypatch.setattr(BagelExit, 'execute', lambda self: ok('exit'))
    monkeypatch.setattr(BagelReturn, 'execute', lambda self: ok('return'))

    def navigate_ok(self: BagelNavigate) -> OperationResult:
        if self.coordinate_only:
            return ok('move', BagelNavigate.STATUS_WAYPOINT)
        if self.destination == 'safe':
            return ok('navigate_safe', BagelNavigate.STATUS_ARRIVED_SAFE)
        return ok('navigate', BagelNavigate.STATUS_ARRIVED_BOX)

    monkeypatch.setattr(BagelNavigate, 'execute', navigate_ok)
    monkeypatch.setattr(BagelOpenBox, 'execute', lambda self: ok('open'))
    monkeypatch.setattr(
        BagelStoreSafe, 'execute',
        lambda self: ok('store', BagelStoreSafe.STATUS_DONE),
    )
    def unlock_ok(self: BagelUnlockSafe) -> OperationResult:
        """完整操作模拟交互与解锁，并通过真实通知推进连续执行的步骤。"""
        if self.phase in ('interact', 'full'):
            ok('interact_safe')
        if self.phase == 'interact':
            return OperationResult(True, BagelUnlockSafe.STATUS_READY)
        self._notify_unlock_ready()
        return ok('unlock', BagelUnlockSafe.STATUS_UNLOCKED)

    monkeypatch.setattr(BagelUnlockSafe, 'execute', unlock_ok)
    monkeypatch.setattr(BagelCloseSearch, 'execute', lambda self: ok('close'))
    monkeypatch.setattr(
        BagelSettleWarehouse, 'execute',
        lambda self: ok('settle', BagelSettleWarehouse.STATUS_DONE),
    )
    return config, record, events


@pytest.mark.parametrize('scene,chain', [
    ('雅努斯出生-r01-39s', [
        'move', 'navigate', 'open', 'store', 'close',
        'move', 'move', 'move', 'navigate_safe', 'interact_safe',
        'unlock', 'store', 'close',
    ]),
    ('白鸽工地出生-20260921-seq5s', ['navigate', 'open', 'store', 'close']),
], ids=['video_store', 'white_dove'])
@pytest.mark.parametrize('limit', [1, 2])
def test_app_published_paths_return_before_reentry(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch, scene: str, chain: list[str], limit: int,
) -> None:
    """两出生点派发各自发布流程，每局结算返回后再开下一局。"""
    config, record, events = app_setup
    config.max_success_rounds = limit
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    controller.set_phases([{'frame': ('贝果-局内', scene)}])
    op = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == f'已成功入仓 {limit} 局'
        assert events == ['enter', *chain, 'exit', 'settle', 'return'] * limit
        assert op.success_rounds == limit
    finally:
        reset_running_state(test_context, op)


def test_app_non_a_restarts_then_collects(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非 A 先退出返回，再入场命中 A 后走收集链。"""
    config, record, events = app_setup
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    scenes = ['雅努斯出生-r02-32s', '雅努斯出生-r01-39s']

    def enter(self: BagelEnter) -> OperationResult:
        events.append('enter')
        controller.set_phases([{'frame': ('贝果-局内', scenes.pop(0))}])
        return OperationResult(True)

    monkeypatch.setattr(BagelEnter, 'execute', enter)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r02-32s')}])
    op = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert events == [
            'enter', 'exit', 'return', 'enter',
            'move', 'navigate', 'open', 'store', 'close',
            'move', 'move', 'move', 'navigate_safe', 'interact_safe',
            'unlock', 'store', 'close', 'exit', 'settle', 'return',
        ]
        assert op.success_rounds == 1
    finally:
        reset_running_state(test_context, op)


def test_app_zero_limit_continues_after_success(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """填 0 时成功入仓两局后仍尝试进入下一局，不因成功次数结束。"""
    config, record, events = app_setup
    config.max_success_rounds = 0
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    op = WatchedApp(test_context, config, record)
    op.watchdog_max_rounds = 52
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert op.success_rounds >= 2
        assert events.count('enter') > 2
        assert events.count('return') >= 2
    finally:
        reset_running_state(test_context, op)


def test_app_empty_safe_does_not_count_success(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """连续空箱可返回入口重试，但不得凑足成功局数。"""
    config, record, events = app_setup
    config.max_success_rounds = 2
    monkeypatch.setattr(
        BagelSettleWarehouse, 'execute',
        lambda self: OperationResult(True, BagelDeposit.STATUS_EMPTY),
    )
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    op = WatchedApp(test_context, config, record)
    op.watchdog_max_rounds = 65
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '连续 3 局安全箱为空' in result.status
        assert op.success_rounds == 0
        assert op.empty_rounds == 3
        assert events.count('enter') == 3
        assert events.count('return') == 3
    finally:
        reset_running_state(test_context, op)


def test_app_interrupted_store_exits_and_reenters(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    no_round_wait: None,
) -> None:
    """实拍受击发生在拖拽核对时：首局退出入仓不计成功，下一局继续完整流程。"""
    config, record, events = app_setup
    controller = BagelDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    attempts = 0
    drags: list[tuple[Point | None, Point]] = []
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])

    def enter(self: BagelEnter) -> OperationResult:
        """每次入场恢复 A 出生图，防止复用受击现场。"""
        nonlocal attempts
        attempts += 1
        assert attempts <= 2
        events.append('enter')
        controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
        return OperationResult(True)

    def open_box(self: BagelOpenBox) -> OperationResult:
        """首局真实搜查图在拖拽后切成受击现场。"""
        events.append('open')
        if attempts == 1:
            controller.set_phases([
                {'frame': ('贝果-局内', '武备箱待入箱-实机'), 'exit': ('on_drag',)},
                {'frame': ('贝果-局内', '武备箱搜查受击中断-20261001')},
            ])
        return OperationResult(True)

    def store(self: BagelStoreSafe) -> OperationResult:
        """首局走真实入箱操作，其余收集使用已有流程替身。"""
        events.append('store')
        if attempts == 1:
            result = BagelOperation.execute(self)
            drags.extend(controller.recorded_drags)
            return result
        return OperationResult(True, BagelStoreSafe.STATUS_DONE)

    monkeypatch.setattr(BagelEnter, 'execute', enter)
    monkeypatch.setattr(BagelOpenBox, 'execute', open_box)
    monkeypatch.setattr(BagelStoreSafe, 'execute', store)
    op = WatchedApp(test_context, config, record)
    op.watchdog_max_rounds = 60
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert attempts == 2
        assert op.success_rounds == 1
        assert op.defeat_rounds == 1
        assert op.failure_retries_used == 1
        assert len(drags) == 1
        assert events[:events.index('enter', 1)] == [
            'enter', 'move', 'navigate', 'open', 'store', 'exit', 'settle', 'return',
        ]
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('rounds,limit,success,expected_count', [
    (['defeat', 'defeat', 'success', 'defeat', 'defeat', 'success'], 2, True, 2),
    (['defeat', 'skip', 'defeat', 'empty', 'defeat'], 1, False, 0),
    (['defeat', 'success'], 1, True, 1),
    (['interrupted', 'defeat', 'interrupted'], 1, False, 0),
    (['interrupted', 'success'], 1, True, 1),
])
def test_app_success_and_skip_do_not_reset_failure_retries(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch, rounds: list[str], limit: int,
    success: bool, expected_count: int,
) -> None:
    """成功、非支持出生点和空箱均不清零；失败有物入仓仍不计成功。"""
    config, record, events = app_setup
    config.max_success_rounds = limit
    config.max_failure_retries = 5 if success else 2
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    round_idx = -1
    original_navigate = BagelNavigate.execute

    def enter(self: BagelEnter) -> OperationResult:
        """按局切换真实出生截图，超出剧本就让测试失败。"""
        nonlocal round_idx
        round_idx += 1
        scene = '雅努斯出生-r02-32s' if rounds[round_idx] == 'skip' else '雅努斯出生-r01-39s'
        events.append('enter')
        controller.set_phases([{'frame': ('贝果-局内', scene)}])
        return OperationResult(True)

    def navigate(self: BagelNavigate) -> OperationResult:
        """只有指定局撤离失败，其余照常完成收集。"""
        if rounds[round_idx] in ('defeat', 'interrupted'):
            status = (BagelOperation.STATUS_DEFEATED if rounds[round_idx] == 'defeat'
                      else BagelOperation.STATUS_INTERRUPTED)
            return OperationResult(False, status)
        return original_navigate(self)

    def settle(self: BagelSettleWarehouse) -> OperationResult:
        """失败局即使带回物资也不能计入成功局数。"""
        events.append('settle')
        status = BagelDeposit.STATUS_EMPTY if rounds[round_idx] == 'empty' else BagelDeposit.STATUS_DONE
        return OperationResult(True, status)

    monkeypatch.setattr(BagelEnter, 'execute', enter)
    monkeypatch.setattr(BagelNavigate, 'execute', navigate)
    monkeypatch.setattr(BagelSettleWarehouse, 'execute', settle)
    op = WatchedApp(test_context, config, record)
    op.watchdog_max_rounds = 130
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success is success, result.status
        assert events.count('enter') == len(rounds)
        assert events.count('settle') == len(rounds) - rounds.count('skip')
        assert events.count('return') == len(rounds) - (not success)
        assert op.success_rounds == expected_count
        assert op.defeat_rounds == rounds.count('defeat') + rounds.count('interrupted')
        assert op.failure_retries_used == op.defeat_rounds - (not success)
        if not success:
            assert '整体重试已用 2/2' in result.status
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('failed_stage', [BagelExit, BagelSettleWarehouse, BagelReturn])
def test_app_defeat_cleanup_error_stops_without_reentry(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch, failed_stage: type[BagelOperation],
) -> None:
    """失败局退出、结算或返回出错时保留原始错误，不重开或伪报达到失败上限。"""
    config, record, events = app_setup
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    monkeypatch.setattr(
        BagelNavigate, 'execute',
        lambda self: OperationResult(False, BagelOperation.STATUS_DEFEATED),
    )
    monkeypatch.setattr(
        failed_stage, 'execute', lambda self: OperationResult(False, '收尾核验失败'),
    )
    op = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '收尾核验失败' in result.status
        assert BagelOperation.STATUS_DEFEATED in result.status
        assert events.count('enter') == 1
        assert op.success_rounds == 0
        if failed_stage in (BagelExit, BagelSettleWarehouse):
            assert 'return' not in events
        if failed_stage is BagelExit:
            assert 'settle' not in events
    finally:
        reset_running_state(test_context, op)
