from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from test.conftest import TestContext

    from one_dragon.base.operation.operation_base import OperationResult


class UnlockController(FixtureController):
    """交互按键只在指定帧推进，光圈动画按截图次数推进。"""

    def __init__(self, ctx: TestContext) -> None:
        """记录按键发生的原图和时长，避免漏按后剧本仍然成功。"""
        super().__init__(ctx)
        self.shown_frame: str = ''
        self.presses: list[tuple[str, float | None]] = []
        self.frames: list[str] = []

    def screenshot(self, independent: bool = False) -> tuple[float, MatLike]:
        """记录实际交给操作的帧，轮询推进后的当前阶段可能已不同。"""
        self.shown_frame = self._phases[self.phase_idx]['frame'][1]
        self.frames.append(self.shown_frame)
        return super().screenshot(independent)

    def interact(
        self, press: bool = False, press_time: float | None = None, release: bool = False,
    ) -> None:
        """只记录 F，不发送真实输入；对应时长正确才让游戏进入下一帧。"""
        self.recorded_inputs.append('f')
        self.presses.append((self.shown_frame, press_time))
        if press and release and self._phases[self.phase_idx].get('press_time') == press_time:
            self._advance_phase()


class WatchedUnlock(WatchdogOperationMixin, BagelUnlockSafe):
    """接错边或少按一次时，及时结束真实执行循环。"""

    watchdog_max_rounds: int = 40


@pytest.fixture
def unlock_controller(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
) -> UnlockController:
    """保留真实画面识别，只替换游戏控制器与等待。"""
    controller = UnlockController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return controller


def ring_phases(cycles: int) -> list[dict]:
    """共用十二张录像帧，每次命中必须按 F，反馈重复一帧防止重复按键。"""
    phases: list[dict] = []
    for cycle in range(1, cycles + 1):
        phases.extend([
            {'frame': ('贝果-局内', f'电子保险箱第{cycle}轮小圈'),
             'exit': ('on_polls', 2 if cycle == 1 else 1)},
            {'frame': ('贝果-局内', f'电子保险箱第{cycle}轮命中'), 'press_time': 0.05},
            {'frame': ('贝果-局内', f'电子保险箱第{cycle}轮反馈'), 'exit': ('on_polls', 2)},
        ])
    return phases


def execute(op: BagelUnlockSafe) -> OperationResult:
    """运行真实节点图，结束后恢复共享上下文的停止状态。"""
    enter_running_state(op.ctx)
    try:
        return op.execute()
    finally:
        reset_running_state(op.ctx, op)


def test_unlock_prompt_uses_actual_frame(test_context: TestContext) -> None:
    """录像中精确点按提示必须被实际区域识别，不模拟识别成功。"""
    root = next(path for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')
    test_context.add_mock_screenshot(cv2_utils.read_image(str(
        root / 'screens/贝果-局内/电子保险箱解锁中-录像.webp',
    )))
    op = BagelUnlockSafe(test_context)
    op.screenshot()
    assert op.wait_unlock_ui().status == '已在解锁界面'


@pytest.mark.parametrize('hits_done', [0, 1, 2, 3])
def test_interruption_never_sends_another_key(
    test_context: TestContext, unlock_controller: UnlockController, hits_done: int,
) -> None:
    """真实执行在任一轮被打回 HUD 后停止，不把剩余 F 发给局内交互。"""
    phases = ring_phases(hits_done) or [
        {'frame': ('贝果-局内', '电子保险箱第1轮小圈'), 'exit': ('on_polls', 2)},
    ]
    phases.append({'frame': ('贝果-局内', '电子保险箱交互-HUD错字-20260930')})
    unlock_controller.set_phases(phases)
    op = WatchedUnlock(test_context, phase='unlock')

    result = execute(op)

    assert not result.success and result.status == '解锁界面消失，无法点按'
    assert op.hits_done == hits_done
    assert unlock_controller.presses == [
        (f'电子保险箱第{cycle}轮命中', 0.05) for cycle in range(1, hits_done + 1)
    ]
    assert unlock_controller.recorded_clicks == []


@pytest.mark.parametrize('phase', ['unlock', 'full'])
def test_video_four_cycles_press_once_each(
    test_context: TestContext, unlock_controller: UnlockController, phase: str,
) -> None:
    """真实 execute 回放四轮录像；每轮只按一次，四次按完还要等搜查面板。"""
    interaction = '电子保险箱交互-HUD错字-20260930'
    phases = [] if phase == 'unlock' else [
        {'frame': ('贝果-局内', interaction), 'press_time': 0.2},
        {'frame': ('贝果-局内', interaction), 'exit': ('on_polls', 2)},
    ]
    phases.extend(ring_phases(4))
    phases.append({'frame': ('贝果-局内', '电子保险箱搜索完成')})
    unlock_controller.set_phases(phases)
    op = WatchedUnlock(test_context, phase=phase)

    result = execute(op)

    assert result.success and result.status == op.STATUS_UNLOCKED
    assert op.hits_done == 4
    expected = [] if phase == 'unlock' else [(interaction, 0.2)]
    expected.extend((f'电子保险箱第{cycle}轮命中', 0.05) for cycle in range(1, 5))
    assert unlock_controller.presses == expected
    assert unlock_controller.frames[-1] == '电子保险箱搜索完成'
    assert all(unlock_controller.frames.count(f'电子保险箱第{cycle}轮反馈') == 2 for cycle in range(1, 5))
    assert unlock_controller.recorded_clicks == []


def test_interact_phase_stops_at_unlock_ui(
    test_context: TestContext, unlock_controller: UnlockController,
) -> None:
    """交互阶段等待光圈出现后结束，不继续按解锁键或等待搜查。"""
    interaction = '电子保险箱交互-HUD错字-20260930'
    unlock_controller.set_phases([
        {'frame': ('贝果-局内', interaction), 'press_time': 0.2},
        {'frame': ('贝果-局内', interaction), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '电子保险箱第1轮小圈')},
    ])
    op = WatchedUnlock(test_context, phase='interact')

    result = execute(op)

    assert result.success and result.status == op.STATUS_READY
    assert op.hits_done == 0
    assert unlock_controller.presses == [(interaction, 0.2)]
    assert unlock_controller.frames == [interaction] * 3 + ['电子保险箱第1轮小圈']
    assert unlock_controller.recorded_clicks == []


def test_large_ring_without_new_cycle_does_not_press(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """启动时只有大圈或上轮残影，必须先观察新一轮小圈，不盲按。"""
    op = BagelUnlockSafe(test_context)
    press = MagicMock()
    monkeypatch.setattr(test_context.controller, 'interact', press)
    test_context.mock_screen('贝果-局内', '电子保险箱第1轮命中')
    op.screenshot()
    assert op.timing_hits().status == '等待光圈进入命中范围'
    press.assert_not_called()
