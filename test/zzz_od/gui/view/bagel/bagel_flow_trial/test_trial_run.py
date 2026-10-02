"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import (
    QApplication,
)

from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.base.operation.one_dragon_context import (
    ContextKeyboardEventEnum,
    OneDragonContext,
)
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_flow import (
    load_published_flow,
)
from zzz_od.gui.view.bagel.bagel_flow_trial import FlowTrialWorker


@pytest.mark.parametrize('phase,key', [
    ('initializing', 'f10'), ('waiting', 'f8'), ('running', 'f8'),
])
def test_main_program_stop_key_cancels_trial(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, key: str, phase: str,
) -> None:
    """通过主程序按键处理取消准备或执行，结束后解除本次事件订阅。"""
    bus = ContextEventBus()
    ctx = MagicMock(current_instance_idx=99, key_stop_running=key, key_start_running='f9')
    ctx.listen_event.side_effect = bus.listen_event
    ctx.unlisten_event.side_effect = bus.unlisten_event
    ctx.dispatch_event.side_effect = bus.dispatch_event
    ctx.run_context.start_running.return_value = True
    worker = FlowTrialWorker(99, load_published_flow('janus_high_b'), ('spawn',), ctx)

    def press_stop() -> None:
        """只调用主程序入口，不直接调用工具停止方法。"""
        OneDragonContext._on_key_press(ctx, 'f9')
        assert not worker.stop_requested.is_set()
        OneDragonContext._on_key_press(ctx, key)
        assert worker.stop_requested.wait(2)

    def wait_for_mouse() -> bool:
        """模拟切窗前等待。"""
        if phase == 'waiting':
            press_stop()
        return not worker.stop_requested.is_set()

    def execute() -> OperationResult:
        """模拟执行期间收到主程序停止键。"""
        press_stop()
        return OperationResult(False, '用户停止')

    if phase == 'initializing':
        ctx.controller = None
        ctx.one_dragon_config.instance_list = [SimpleNamespace(idx=99)]
        ctx.init_ocr.side_effect = press_stop
    monkeypatch.setattr(worker, '_wait_for_mouse_release', wait_for_mouse)
    execute_mock = MagicMock(side_effect=execute)
    cleanup = MagicMock()
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_flow_trial.BagelRunFlow.execute', execute_mock)
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_flow_trial.release_flow_inputs', cleanup)
    worker.run()
    assert not bus.callbacks[ContextKeyboardEventEnum.PRESS.value]
    assert worker.stop_requested.is_set()
    if phase == 'running':
        execute_mock.assert_called_once()
        cleanup.assert_called_once_with(ctx)
        assert ctx.run_context.stop_running.call_count == 2
    else:
        ctx.run_context.start_running.assert_not_called()
        execute_mock.assert_not_called()
        cleanup.assert_not_called()
        ctx.run_context.stop_running.assert_called_once()


def test_worker_cleanup_and_record(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """业务异常仍清理运行状态与输入，记录包含快照。"""
    ctx = MagicMock(current_instance_idx=99)
    ctx.run_context.start_running.return_value = True
    monkeypatch.setattr(FlowTrialWorker, '_wait_for_mouse_release', lambda _: True)
    cleanup = MagicMock()
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_flow_trial.release_flow_inputs', cleanup)
    monkeypatch.setattr(
        'zzz_od.gui.view.bagel.bagel_flow_trial.BagelRunFlow.execute',
        MagicMock(side_effect=RuntimeError('模拟失败')),
    )
    worker = FlowTrialWorker(
        99, load_published_flow('janus_high_b'), ('open_box', 'store_box'), ctx
    )
    worker.run()
    cleanup.assert_called_once_with(ctx)
    ctx.run_context.stop_running.assert_called_once()
    events = [json.loads(line) for line in worker.record_path.read_text(encoding='utf-8').splitlines()]
    assert events[0] == {
        'kind': 'snapshot', 'flow': worker.flow.to_dict(), 'step_ids': list(worker.step_ids),
    }
    assert events[-1]['kind'] == 'trial_finished'


@pytest.mark.parametrize('scenario', ['release', 'cancel', 'held', 'idle'])
def test_trial_waits_for_mouse_release_before_activating_game(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, scenario: str,
) -> None:
    """启动时左键仍按住或再次点击，不能把输入带入刚激活的游戏。"""
    import ctypes

    clock = [0.0]
    activated: list[float] = []
    ctx = MagicMock(current_instance_idx=99)

    def start() -> bool:
        """记录真实试跑入口何时请求激活游戏。"""
        activated.append(clock[0])
        return True

    ctx.run_context.start_running.side_effect = start

    def mouse_state(key: int) -> int:
        """覆盖单击后松开、双击和一直按住。"""
        assert key == 0x01
        if scenario == 'idle':
            return 0
        return 0x8000 if scenario == 'held' or clock[0] < 0.12 or 0.2 <= clock[0] < 0.3 else 0

    monkeypatch.setattr(
        ctypes.windll.user32, 'GetAsyncKeyState', mouse_state,
    )
    monkeypatch.setattr(
        'zzz_od.gui.view.bagel.bagel_flow_trial.time',
        SimpleNamespace(monotonic=lambda: clock[0]),
    )
    cleanup = MagicMock()
    execute = MagicMock(return_value=OperationResult(True, '检查完成'))
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_flow_trial.release_flow_inputs', cleanup)
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_flow_trial.BagelRunFlow.execute', execute)
    worker = FlowTrialWorker(99, load_published_flow('janus_high_b'), ('spawn',), ctx)

    def wait(timeout: float) -> bool:
        """用可控时间模拟松键、再次点击及等待中取消。"""
        clock[0] += timeout
        if scenario == 'cancel':
            worker.stop()
        return worker.stop_requested.is_set()

    monkeypatch.setattr(worker.stop_requested, 'wait', wait)
    worker.run()
    if scenario in ('cancel', 'held'):
        assert activated == []
        execute.assert_not_called()
        cleanup.assert_not_called()
        if scenario == 'held':
            assert clock[0] >= 5
            assert '鼠标左键持续按下' in worker.record_path.read_text(encoding='utf-8')
    else:
        minimum = 0.3 if scenario == 'idle' else 0.6
        assert len(activated) == 1 and activated[0] >= minimum
        execute.assert_called_once()
    ctx.controller.click.assert_not_called()
    ctx.controller.normal_attack.assert_not_called()


def test_cancel_before_start_never_controls_game(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """初始化前停止不应占用运行状态或发送松键。"""
    ctx = MagicMock(current_instance_idx=99)
    cleanup = MagicMock()
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_flow_trial.release_flow_inputs', cleanup)
    worker = FlowTrialWorker(99, load_published_flow('janus_high_b'), ('spawn',), ctx)
    worker.stop()
    worker.run()
    ctx.run_context.start_running.assert_not_called()
    cleanup.assert_not_called()
