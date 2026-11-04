from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.base.controller.window_error import WindowAmbiguousError
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult


class WindowContext(SimpleNamespace):
    @property
    def is_game_window_ready(self) -> bool:
        return self.ready()


class WindowOperation(Operation):
    @operation_node(name='测试开始', is_start_node=True, screenshot_before_round=False)
    def start(self) -> OperationRoundResult:
        return self.round_success('已运行')


@pytest.mark.parametrize('state', ['ready', 'missing', 'ambiguous'])
def test_window_check_routes_only_missing_to_startup(state: str) -> None:
    ready = Mock(return_value=state == 'ready')
    if state == 'ambiguous':
        ready.side_effect = WindowAmbiguousError('找到多个游戏窗口')
    ctx = WindowContext(
        ready=ready, controller=SimpleNamespace(game_win=SimpleNamespace(win_title='候选标题')),
        run_context=SimpleNamespace(is_context_stop=False, is_context_pause=False,
                                    event_bus=Mock(), current_app_id=None, notify_pool=Mock()),
        notify_config=SimpleNamespace(enable_notify=False),
        unlisten_all_event=Mock(),
    )
    startup = Mock()
    startup.execute.return_value = OperationResult(True)
    operation = WindowOperation(ctx, op_to_enter_game=startup)
    result = operation.execute()
    if state == 'missing':
        startup.execute.assert_called_once()
    else:
        startup.execute.assert_not_called()
    assert result.success == (state != 'ambiguous')
    assert result.status == ('找到多个游戏窗口' if state == 'ambiguous' else '已运行')
