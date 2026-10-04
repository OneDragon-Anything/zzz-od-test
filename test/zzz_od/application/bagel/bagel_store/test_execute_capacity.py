from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import TransferController, running_operation
from test.harness.bagel_safe_slots import (
    copy_safe_slot,
    lock_safe_suffix,
    native_four_slot_screen,
)
from test.harness.fixture_controller import WatchdogOperationMixin

from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext

    from one_dragon.base.geometry.point import Point


class SafeDragController(TransferController):
    """用完整截图推进拖拽前后两帧，只记录输入。"""

    def __init__(self, ctx: TestContext) -> None:
        """记录目标格，验证没有操作锁定位置。"""
        super().__init__(ctx)
        self.drags: list[Point] = []

    def drag_to(
        self, end: Point, start: Point | None = None, duration: float = 0.5, press_time: float = 0,
    ) -> None:
        """只在拖拽阶段推进，额外拖拽会被最终断言捕获。"""
        self.drags.append(end)
        if self._current_exit() == ('on_drag',):
            self._advance_phase()


class WatchedSafeStore(WatchdogOperationMixin, BagelStoreSafe):
    """限制完整收集流程的轮数。"""

    watchdog_max_rounds: int = 20


@pytest.mark.parametrize('capacity', [2, 3, 4, 5])
@pytest.mark.parametrize('swap', [False, True])
def test_store_fills_or_swaps_only_unlocked_slots(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
    capacity: int, swap: bool,
) -> None:
    """实拍像素合成容量场景，完整执行最后一格入箱或满箱对换及回读。"""
    pending = test_context.load_screen('贝果-局内', '武备箱待入箱-实机')
    native = native_four_slot_screen()
    before = pending.copy()
    # 清空结果，用同一件 S 贵重物品占两个结果格；第二件应因满箱且无升级而留下。
    for center in RESULT_SLOT_CENTERS:
        copy_safe_slot(before, pending, RESULT_SLOT_CENTERS[4], center)
    for center in SAFE_SLOT_CENTERS[:capacity - 1]:
        copy_safe_slot(before, native, SAFE_SLOT_CENTERS[0], center)
    if swap:
        copy_safe_slot(before, pending, RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[capacity - 1])
    for center in RESULT_SLOT_CENTERS[:2]:
        copy_safe_slot(before, native, SAFE_SLOT_CENTERS[0], center)
    before = lock_safe_suffix(before, capacity)
    after = before.copy()
    if swap:
        copy_safe_slot(after, pending, RESULT_SLOT_CENTERS[0], RESULT_SLOT_CENTERS[0])
    else:
        copy_safe_slot(after, pending, RESULT_SLOT_CENTERS[4], RESULT_SLOT_CENTERS[0])
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
    assert [point.tuple() for point in controller.drags] == [SAFE_SLOT_CENTERS[capacity - 1].tuple()]
    assert controller.recorded_clicks == []
