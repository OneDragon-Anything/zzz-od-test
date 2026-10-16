from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation import Operation
from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_operation import BagelRecoverableFailure
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow
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


class WatchedFlow(WatchdogOperationMixin, BagelRunFlow):
    """连续解锁仍运行真实执行器，错误流转用轮次上限结束。"""

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


@pytest.mark.parametrize(
    'hits_done',
    [
        2,
    ],
)
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


@pytest.mark.parametrize(
    'outcome',
    [
        'success',
        'interrupted',
        'unlock_timeout',
    ],
)
def test_continuous_flow_keeps_first_ring_and_stage_events(
    test_context: TestContext, unlock_controller: UnlockController,
    monkeypatch: pytest.MonkeyPatch, outcome: str,
) -> None:
    """从真实箱前交互贯穿连续解锁，核对输入、阶段事件和中断原因。"""
    interaction = '电子保险箱交互-HUD错字-20260930'
    search = '电子保险箱搜索完成'
    phases = [{'frame': ('贝果-局内', interaction), 'press_time': 0.2}]
    if outcome == 'existing_search':
        phases.append({'frame': ('贝果-局内', search)})
    else:
        phases.append({'frame': ('贝果-局内', interaction), 'exit': ('on_polls', 2)})
        cycles = ring_phases(1 if outcome == 'interrupted' else 4)
        cycles[0]['exit'] = ('on_polls', 1)
        phases.extend(cycles)
        final_frame = {
            'success': search, 'interrupted': interaction,
            'unlock_timeout': '电子保险箱第4轮反馈',
        }[outcome]
        phases.append({'frame': ('贝果-局内', final_frame)})
    unlock_controller.set_phases(phases)
    monkeypatch.setattr(WatchedUnlock, 'watchdog_max_rounds', 100)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelUnlockSafe', WatchedUnlock)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.release_flow_inputs', lambda _: None)
    flow = load_published_flow('janus_high_a')
    selected = tuple(s.id for s in flow.steps if s.target == 'safe' and s.action in ('interact', 'unlock'))
    events: list[dict[str, object]] = []
    op = WatchedFlow(
        test_context, flow, selected, on_event=events.append, continuous_safe_unlock=True,
    )
    build = MagicMock(wraps=op.build_operation)
    monkeypatch.setattr(op, 'build_operation', build)
    waits: list[tuple[int, float | None]] = []
    original_wait = Operation._after_round_wait

    def record_wait(
        operation: Operation, wait: float | None = None, wait_round_time: float | None = None,
    ) -> None:
        """保留受控等待时钟，记录首轮输入前是否存在固定观察空档。"""
        waits.append((len(unlock_controller.presses), wait))
        original_wait(operation, wait=wait, wait_round_time=wait_round_time)

    monkeypatch.setattr(Operation, '_after_round_wait', record_wait)
    enter_running_state(test_context)
    try:
        result = op.execute()
    finally:
        reset_running_state(test_context, op)

    failed = outcome in ('interrupted', 'unlock_timeout')
    assert result.success is not failed, result.status
    if outcome == 'interrupted':
        assert result.status == op.STATUS_INTERRUPTED
        assert result.data == '解锁界面消失，无法点按'
    elif outcome == 'unlock_timeout':
        assert result.status == op.STATUS_TIMEOUT
        assert isinstance(result.data, BagelRecoverableFailure)
        assert result.data.reason == op.STATUS_TIMEOUT
    build.assert_called_once_with(next(s for s in flow.steps if s.id == selected[0]))
    expected = [(interaction, 0.2)]
    hits = 0 if outcome == 'existing_search' else 1 if outcome == 'interrupted' else 4
    expected.extend((f'电子保险箱第{cycle}轮命中', 0.05) for cycle in range(1, hits + 1))
    assert unlock_controller.presses == expected
    assert all((wait or 0) <= 0.02 for presses, wait in waits if presses == 1)
    assert [(e['kind'], e['step_id']) for e in events if e['kind'] in ('start', 'done', 'failed')] == [
        ('start', selected[0]), ('done', selected[0]),
        ('start', selected[1]), ('failed' if failed else 'done', selected[1]),
    ]
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
