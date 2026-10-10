from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.utils import cv2_utils
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
)
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_close_search import BagelCloseSearch
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
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
    destination: MatLike,
    source: MatLike,
    src_center: Point,
    dst_center: Point,
) -> None:
    """把源格占用裁剪和左上角标窗贴到目标格，避免合成帧类型错位。"""
    patch = slot_crop(source, src_center, half=40)
    if patch is None:
        raise AssertionError('缺少格子裁剪')
    half = patch.shape[0] // 2
    x1 = int(dst_center.x) - half
    y1 = int(dst_center.y) - half
    destination[y1 : y1 + patch.shape[0], x1 : x1 + patch.shape[1]] = patch
    badge = 40
    offset = 52
    sx1 = int(src_center.x) - offset
    sy1 = int(src_center.y) - offset
    dx1 = int(dst_center.x) - offset
    dy1 = int(dst_center.y) - offset
    destination[dy1 : dy1 + badge, dx1 : dx1 + badge] = source[
        sy1 : sy1 + badge, sx1 : sx1 + badge
    ]


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


class WatchedDeposit(WatchdogOperationMixin, BagelDeposit):
    """限制入仓轮数。"""

    watchdog_max_rounds: int = 25


class WatchedApp(WatchdogOperationMixin, BagelApp):
    """限制单局编排轮数。"""

    watchdog_max_rounds: int = 40


@pytest.fixture
def controller(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> BagelDragController:
    """使用真截图与 OCR，替换输入并允许拖拽推进。"""
    result = BagelDragController(test_context)
    monkeypatch.setattr(test_context, 'controller', result)
    return result


class WatchedCloseSearch(WatchdogOperationMixin, BagelCloseSearch):
    """独立关闭流程使用有界看门狗。"""

    watchdog_max_rounds: int = 20


def _fill_slots(
    destination: MatLike, source: MatLike, src_center: Point, centers: tuple[Point, ...]
) -> None:
    """把同一件物品贴满一组格子。"""
    for center in centers:
        _copy_item(destination, source, src_center, center)


def _clicks_in_area(
    test_context: TestContext, controller: BagelDragController, area_name: str
) -> int:
    """统计落在仓库文字区内的点击次数。"""
    rect = test_context.screen_loader.get_area('贝果-仓库', area_name).pc_rect
    return sum(
        1
        for point in controller.recorded_clicks
        if rect.x1 <= point.x <= rect.x2 and rect.y1 <= point.y <= rect.y2
    )


@pytest.fixture
def app_setup(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[BagelConfig, BagelRunRecord, list[str]]:
    """注入默认出生画面和子操作替身，验证正式任务的编排顺序。"""
    controller = FixtureController(test_context)
    controller.set_phases([{'frame': ('贝果-局内', '高危A出生-原生1080')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_run_flow.BagelRunFlow.precondition',
        lambda *_: None,
    )
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_app.release_flow_inputs', lambda _: None
    )
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_run_flow.release_flow_inputs', lambda _: None
    )
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
        BagelStoreSafe,
        'execute',
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
        BagelSettleWarehouse,
        'execute',
        lambda self: ok('settle', BagelSettleWarehouse.STATUS_DONE),
    )
    return config, record, events
