from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    reset_running_state,
)

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    LostVoidMoveByDet,
)

if TYPE_CHECKING:
    from cv2.typing import MatLike


class _EscapeController(FixtureController):
    """普通攻击后仍保持受阻，横移时才进入可交互状态。"""

    def __init__(self, ctx: MagicMock) -> None:
        """建立固定帧剧本和可观察的动作反馈。"""
        super().__init__(ctx)
        self.clock: float = time.time()
        self.attack_count: int = 0
        self.escaped: bool = False
        self.moving: bool = False
        self.drift_target: bool = False
        self.set_phases([{'frame': ('迷失之地-大世界', '玛琳前-以太稳定')}])

    def screenshot(self, independent: bool = False) -> tuple[float, MatLike]:
        """每次截图推进模拟时钟，避免依赖真实等待。"""
        _, frame = super().screenshot(independent)
        self.clock += 0.5
        return self.clock, frame

    def start_moving_forward(self) -> None:
        """记录前进指令，不操作真实设备。"""
        self.moving = True
        if self.drift_target:
            target = self.ctx.lost_void.detect_to_go.return_value.results[0]
            target.x1, target.x2 = 1200, 1240

    def stop_moving_forward(self) -> None:
        """模拟释放前进键。"""
        self.moving = False

    def move_mouse_relative(self, dx: float, dy: float) -> None:
        """静止转向时让目标居中，移动时保持偏移以反复触发跟随。"""
        if not self.moving:
            target = self.ctx.lost_void.detect_to_go.return_value.results[0]
            target.x1, target.x2 = 940, 980

    def normal_attack(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """攻击没有清除障碍，用于验证后续换方向。"""
        self.attack_count += 1

    def move_a(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """横移成功后允许交互到位。"""
        if press:
            self.escaped = True


class _WatchedMove(WatchdogOperationMixin, LostVoidMoveByDet):
    """给实际节点循环加轮数上限。"""


@pytest.mark.parametrize('off_center', [False, True])
@pytest.mark.parametrize('animated', [False, True])
@pytest.mark.parametrize('continuous_motion', [False, True])
def test_stuck_attack_then_escape_reaches_target(
    moving_op: LostVoidMoveByDet,
    monkeypatch: pytest.MonkeyPatch,
    blocked_animation_frames: list[MatLike],
    takeoff_frame: MatLike,
    off_center: bool,
    animated: bool,
    continuous_motion: bool,
) -> None:
    """完整运行移动→受阻→攻击→换方向→重新识别→实际到达目标。"""
    ctx = moving_op.ctx
    ctx.load_screen.return_value = moving_op.last_screenshot
    if animated:
        ctx.load_screen.side_effect = lambda screen_name, state: blocked_animation_frames[ctx.load_screen.call_count % 2]
    if continuous_motion:
        ctx.load_screen.side_effect = None
        ctx.load_screen.return_value = takeoff_frame
    controller = _EscapeController(ctx)
    controller.drift_target = off_center
    ctx.controller = controller
    ctx.run_context.is_context_stop = False
    ctx.run_context.is_context_pause = False
    ctx.is_game_window_ready = True
    ctx.debug_trace_bus = None
    if off_center:
        target = ctx.lost_void.detect_to_go.return_value.results[0]
        target.x1, target.x2 = 1200, 1240
    op = _WatchedMove(ctx, LostVoidRegionType.ENTRY, moving_op.target_type, allow_arrival_by_interact_btn=True)
    op.watchdog_max_rounds = 70
    op._init_watchdog()
    monkeypatch.setattr(op, '_after_round_wait', MagicMock())
    if continuous_motion:
        # 模拟运行日志中的持续大帧差，时限保护必须独立触发。
        monkeypatch.setattr(op.motion_detector, 'update', lambda image, timestamp: True)

    def find_area(screen: MatLike, screen_name: str, area_name: str) -> OperationRoundResult:
        """只有成功横移后才出现可交互按钮。"""
        found = area_name == '按键-普通攻击' or (area_name == '按键-交互' and controller.escaped)
        return OperationRoundResult(OperationRoundResultEnum.SUCCESS if found else OperationRoundResultEnum.RETRY)

    monkeypatch.setattr(op, 'round_by_find_area', find_area)
    try:
        result = op.execute()
        assert result.success and result.status == op.STATUS_NEED_DETECT
        assert op.stuck_state.recovery_active
        assert op.stuck_state.stuck_times == 1
        next_op = _WatchedMove(
            ctx, LostVoidRegionType.ENTRY, moving_op.target_type,
            allow_arrival_by_interact_btn=True, stuck_state=op.stuck_state,
        )
        next_op._init_watchdog()
        monkeypatch.setattr(next_op, '_after_round_wait', MagicMock())
        monkeypatch.setattr(next_op, 'round_by_find_area', find_area)
        result = next_op.execute()
    finally:
        reset_running_state(ctx, op)
        if 'next_op' in locals():
            reset_running_state(ctx, next_op)
    assert result.success, result.status
    assert controller.attack_count == 1
    assert controller.escaped
    assert op.stuck_state.stuck_times == 0
    assert not op.stuck_state.recovery_active
    assert op.stuck_state.direction_penalties['w'] == 1
