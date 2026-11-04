from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.base.controller import pc_game_window
from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.controller.pc_game_window import PcGameWindow
from zzz_od.operation.enter_game.enter_game import EnterGame


@pytest.mark.parametrize('replacement_appears', [True, False])
def test_enter_game_rechecks_lost_window(
    monkeypatch: pytest.MonkeyPatch, replacement_appears: bool,
) -> None:
    """旧窗口失效时按间隔重试，窗口恢复后继续识别。"""
    old_window = SimpleNamespace(title='绝区零', _hWnd=1)
    new_window = SimpleNamespace(title='绝区零', _hWnd=2)
    find_windows = Mock(return_value=[old_window])
    is_window = Mock(side_effect=lambda hwnd: hwnd == 1)
    monkeypatch.setattr(pc_game_window.pyautogui, 'getWindowsWithTitle', find_windows)
    monkeypatch.setattr(pc_game_window.ctypes.windll.user32, 'IsWindow', is_window)
    controller = PcControllerBase.__new__(PcControllerBase)
    controller.game_win = PcGameWindow()
    controller.game_win.update_win_title('绝区零')
    assert controller.is_game_window_ready

    frame = object()
    capture = Mock(return_value=frame)
    controller.screenshot_controller = SimpleNamespace(
        active_strategy_name='test', get_screenshot=capture,
    )
    controller.screenshot = lambda: (0.0, controller.get_screenshot())
    operation = EnterGame.__new__(EnterGame)
    operation.ctx = SimpleNamespace(controller=controller)
    operation._current_node = EnterGame.check_screen.operation_node_annotation
    operation._after_round_wait = Mock()
    operation.check_game_data_updated = Mock(return_value=None)
    operation.check_enter_click_status_text = Mock(return_value=('点击进入游戏', None))

    capture.side_effect = RuntimeError('截图器内部异常')
    with pytest.raises(RuntimeError, match='截图器内部异常'):
        operation._execute_one_round()
    operation._after_round_wait.assert_not_called()
    capture.reset_mock(side_effect=True)

    find_windows.return_value = []
    is_window.side_effect = lambda hwnd: hwnd == 2
    result = operation._execute_one_round()
    assert result.status == '游戏窗口未就绪'
    operation._after_round_wait.assert_called_once_with(wait=1, wait_round_time=None)
    capture.assert_not_called()
    operation.check_enter_click_status_text.assert_not_called()

    if replacement_appears:
        find_windows.return_value = [new_window]
        result = operation._execute_one_round()
        assert result.is_success
        assert result.status == '点击进入游戏'
        assert controller.game_win.get_hwnd() == 2
        capture.assert_called_once()
        operation.check_enter_click_status_text.assert_called_once_with(frame)
    else:
        result = operation._execute_one_round()
        assert result.status == '游戏窗口未就绪'
        assert operation._after_round_wait.call_count == 2
        capture.assert_not_called()
