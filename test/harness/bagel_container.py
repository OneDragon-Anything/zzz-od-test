"""容器恢复测试共用的存档控制器、子操作看门狗和执行入口。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)
from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow
from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe

if TYPE_CHECKING:
    from collections.abc import Callable

    from cv2.typing import MatLike

    from one_dragon.base.operation.operation_base import OperationResult
    from test.conftest import TestContext

class ContainerController(FixtureController):
    """复用存档识别，仅按松键、短步和 F 推进画面。"""

    def __init__(self, ctx: TestContext) -> None:
        """准备可记录清理的假输入接口，不访问真实键鼠。"""
        super().__init__(ctx)
        self.trace: list[tuple[str, int, int, float]] = []
        self.frames: int = 0
        self.shown_phase: int = 0
        self.keyboard_controller = MagicMock()
        self.btn_controller = MagicMock()
        self.background_mode: bool = False
        self.last_frame: tuple[float, MatLike] | None = None
        self.stale_after_release: bool = False
        self.stale_pending: bool = False
        self.pause_callback: Callable[[], None] | None = None

    @property
    def current_frame(self) -> MatLike:
        """缺提示帧只遮交互区域，HUD 和小地图仍使用原生存档。"""
        image = super().current_frame.copy()
        phase = self._phases[self.phase_idx]
        for area in phase.get('hide', ()):
            screen = '战斗画面' if area == '按键-普通攻击' else '贝果-局内'
            rect = self.ctx.screen_loader.get_area(screen, area).rect
            image[rect.y1:rect.y2, rect.x1:rect.x2] = 0
        return image

    def screenshot(self, independent: bool = False) -> tuple[float, MatLike]:
        """松键后可返回一次旧帧，验证操作不会再次采信动作前提示。"""
        if self.stale_pending:
            self.stale_pending = False
            self.trace.append(('stale', self.shown_phase, self.frames, time.time()))
            assert self.last_frame is not None
            return self.last_frame
        self.frames += 1
        self.shown_phase = self.phase_idx
        self.trace.append(('frame', self.phase_idx, self.frames, time.time()))
        result = super().screenshot(independent)
        self.last_frame = result
        return result

    def stop_moving_forward(self) -> None:
        """提示出现后的第一次松键才推进到停步后的画面。"""
        self.is_moving = False
        self.trace.append(('release', self.phase_idx, self.frames, time.time()))
        if self._phases[self.phase_idx].get('on') == 'release':
            self._advance_phase()
            if self.stale_after_release:
                self.stale_after_release = False
                self.stale_pending = True

    def start_moving_forward(self) -> None:
        """恢复只许短步，持续前进直接使测试失败。"""
        raise AssertionError('容器恢复不得恢复持续前进')

    def turn_by_angle_diff(self, angle_diff: float) -> None:
        """记录转向，面板上不得转向。"""
        assert not self._phases[self.phase_idx].get('panel')
        self.trace.append(('turn', self.phase_idx, self.frames, time.time()))

    def move_w(
        self, press: bool = False, press_time: float | None = None, release: bool = False,
    ) -> None:
        """根据当前位置计算后的短步才能恢复提示。"""
        phase = self._phases[self.phase_idx]
        assert not phase.get('panel')
        assert press and release and press_time == 0.08
        self.trace.append(('w', self.phase_idx, self.frames, time.time()))
        if phase.get('on') == 'w':
            self._advance_phase()

    def interact(
        self, press: bool = False, press_time: float | None = None, release: bool = False,
    ) -> None:
        """首次输入和补按都记录，面板上的全部拾取一律拒绝。"""
        phase = self._phases[self.phase_idx]
        assert not phase.get('panel')
        assert press and release and press_time == 0.2
        self.trace.append(('f', self.phase_idx, self.frames, time.time()))
        if callable(self.pause_callback):
            callback, self.pause_callback = self.pause_callback, None
            callback()
        if phase.get('on') == 'f':
            self._advance_phase()


class WatchedNavigate(WatchdogOperationMixin, BagelNavigate):
    """导航子操作也限制总轮次，不能只依赖父执行器。"""


class WatchedOpenBox(WatchdogOperationMixin, BagelOpenBox):
    """开箱等待即使业务时限失效也必须有限结束。"""


class WatchedUnlockSafe(WatchdogOperationMixin, BagelUnlockSafe):
    """保险箱进入面板的等待也使用既有看门狗。"""


class WatchedFlow(WatchdogOperationMixin, BagelRunFlow):
    """完整执行的等待失败必须有限结束。"""

    watchdog_max_rounds: int = 40


def phases(target: str) -> tuple[dict, dict, dict]:
    """提示与成功面板都用真实存档；消失场景明确标记为合成遮挡。"""
    hint = '白鸽工地箱前-录像8s' if target == 'box' else '电子保险箱F提示'
    ready = '武备箱搜查中-r07' if target == 'box' else '电子保险箱第1轮小圈'
    prompt = {'frame': ('贝果-局内', hint)}
    missing = {**prompt, 'hide': ('交互提示',)}
    panel = {'frame': ('贝果-局内', ready), 'panel': True}
    return prompt, missing, panel


def prepare(
    ctx: TestContext, monkeypatch: pytest.MonkeyPatch, target: str,
    script: list[dict], selection: str = 'both', displacement: float | None = None,
) -> tuple[ContainerController, WatchedFlow, list[dict[str, object]]]:
    """运行真实子操作；位移参数仅用于补充前移、后移分支，默认真实配准。"""
    for name, watched in (
        ('BagelNavigate', WatchedNavigate),
        ('BagelOpenBox', WatchedOpenBox),
        ('BagelUnlockSafe', WatchedUnlockSafe),
    ):
        monkeypatch.setattr(f'zzz_od.application.bagel.bagel_run_flow.{name}', watched)
    controller = ContainerController(ctx)
    controller.set_phases(script)
    monkeypatch.setattr(ctx, 'controller', controller)
    flow = load_published_flow('janus_high_b' if target == 'box' else 'janus_high_a')
    approach = next(s for s in flow.steps if s.action == 'approach' and s.target == target)
    interact = next(s for s in flow.steps if s.action == 'interact' and s.target == target)
    chosen = {'both': (approach.id, interact.id), 'approach': (approach.id,), 'interact': (interact.id,)}[selection]
    events: list[dict[str, object]] = []
    op = WatchedFlow(ctx, flow, chosen, on_event=events.append)
    if displacement is not None:
        real_locate = BagelRouteVision.locate

        def locate(vision: BagelRouteVision, crop: MatLike) -> tuple[float, float] | None:
            """仍执行真实定位，仅缺提示帧注入受控角色位移。"""
            position = real_locate(vision, crop)
            if controller._phases[controller.shown_phase].get('hide') and position is not None:
                x, y = approach.waypoints[0].xy
                return x + displacement, y
            return position

        monkeypatch.setattr(BagelRouteVision, 'locate', locate)
    return controller, op, events


def execute(op: WatchedFlow) -> OperationResult:
    """结束后清理共享上下文，不打开真实游戏。"""
    enter_running_state(op.ctx)
    try:
        return op.execute()
    finally:
        reset_running_state(op.ctx, op)
