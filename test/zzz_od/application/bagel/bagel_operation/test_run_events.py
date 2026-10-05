"""操作结束必须解绑运行事件，并等待已开始的回调完成。"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEventEnum,
)
from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_operation import BagelOperation


class FinishOperation(BagelOperation):
    """只返回结果，避免测试触碰真实控制器。"""

    @operation_node(name='完成', is_start_node=True, screenshot_before_round=False)
    def finish(self) -> OperationRoundResult:
        """正常结束一次操作。"""
        return self.round_success()


@pytest.fixture(params=['operation', 'app'])
def op(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
) -> FinishOperation | BagelApp:
    """两条真实事件总线配合模拟上下文，不连接游戏。"""
    ctx = MagicMock()
    ctx.controller.game_config.get_action_keys.return_value = {'move_w': 'w', 'interact': 'f'}
    ctx.controller.background_mode = False
    ctx.debug_trace_bus = None
    ctx.run_context.is_context_stop = False
    ctx.run_context.is_context_pause = False
    ctx.run_context.is_context_running = True
    ctx.run_context.is_app_need_notify.return_value = False
    ctx.run_context.event_bus = ContextEventBus()
    ctx.unlisten_all_event = ContextEventBus().unlisten_all_event
    finish = FinishOperation(ctx, need_check_game_win=False)
    if request.param == 'operation':
        return finish
    app = BagelApp(ctx, MagicMock(), MagicMock())
    monkeypatch.setattr(app, '_analyse_node_annotations', finish._analyse_node_annotations)
    monkeypatch.setattr(app, 'handle_init', lambda: None)
    return app


@pytest.mark.parametrize('outcome', ['success', 'failure', 'init_error', 'cleanup_error'])
def test_all_exits_remove_run_listeners(
    op: FinishOperation | BagelApp, outcome: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """初始化和收尾异常也不能留下暂停、恢复监听。"""
    if outcome == 'failure':
        monkeypatch.setattr(op, '_execute_one_round', lambda: op.round_fail('失败'))
    elif outcome == 'init_error':
        monkeypatch.setattr(op, 'handle_init', MagicMock(side_effect=ValueError('初始化失败')))
    elif outcome == 'cleanup_error':
        monkeypatch.setattr(op, 'after_operation_done', MagicMock(side_effect=ValueError('收尾失败')))
    if outcome == 'cleanup_error':
        with pytest.raises(ValueError, match='收尾失败'):
            op.execute()
    else:
        assert op.execute().success == (outcome == 'success')
    assert not any(op.ctx.run_context.event_bus.callbacks.values())


def test_queued_callback_cannot_reach_finished_or_reused_operation(
    op: FinishOperation | BagelApp, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已经入队的旧回调，在同一操作再次执行时也不能生效。"""
    bus = op.ctx.run_context.event_bus
    queued = []
    pause = MagicMock()
    monkeypatch.setattr(op, 'handle_pause', pause)
    monkeypatch.setattr(op, 'handle_init', lambda: queued.extend(bus.callbacks[ApplicationRunContextStateEventEnum.PAUSE]))
    assert op.execute().success
    old_callback = queued[0]
    op.ctx.run_context.is_context_running = False
    old_callback(None)
    pause.assert_not_called()

    def restart() -> None:
        old_callback(None)
        op.ctx.run_context.is_context_running = True

    monkeypatch.setattr(op, 'handle_init', restart)
    assert op.execute().success
    pause.assert_not_called()


def test_cleanup_preserves_other_subscribers(op: FinishOperation | BagelApp) -> None:
    """只清理当前贝果执行的监听，不移除同总线上的其他订阅者。"""
    bus = op.ctx.run_context.event_bus
    other = FinishOperation(op.ctx, need_check_game_win=False)
    event = ApplicationRunContextStateEventEnum.PAUSE
    bus.listen_event(event, other._on_pause)
    assert op.execute().success
    assert bus.callbacks[event] == [other._on_pause]
    assert not bus.callbacks[ApplicationRunContextStateEventEnum.RESUME]


def test_running_callback_finishes_before_execute_returns(
    op: FinishOperation | BagelApp, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """用事件阻塞旧暂停清理，执行入口须等清理完成后才能返回。"""
    entered, release, node_done = Event(), Event(), Event()
    bus = op.ctx.run_context.event_bus

    def pause() -> None:
        entered.set()
        assert release.wait(5)

    def finish() -> OperationRoundResult:
        op.ctx.run_context.is_context_running = False
        bus.dispatch_event(ApplicationRunContextStateEventEnum.PAUSE)
        assert entered.wait(5)
        node_done.set()
        return op.round_success()

    monkeypatch.setattr(op, 'handle_pause', pause)
    monkeypatch.setattr(op, '_execute_one_round', finish)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(op.execute)
        try:
            assert node_done.wait(5)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.1)
        finally:
            release.set()
            future.result(timeout=5)
    assert not any(bus.callbacks.values())
