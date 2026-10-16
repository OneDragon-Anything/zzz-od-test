"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import (
    QApplication,
)

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_flow import (
    load_published_flow,
)
from zzz_od.gui.view.bagel.bagel_flow_trial import FlowTrialWorker


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


@pytest.mark.parametrize(
    'scenario',
    [
        'release',
        'cancel',
        'held',
    ],
)
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
