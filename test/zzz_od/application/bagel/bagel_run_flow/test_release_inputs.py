"""收回持续输入和未纳入持续按键集合的定时交互、拖拽。"""

from unittest.mock import MagicMock

import pytest
from pynput import mouse

from zzz_od.application.bagel.bagel_run_flow import release_flow_inputs


def test_release_timed_and_drag_inputs() -> None:
    """只替换底层输入，不会向桌面发送事件。"""
    controller = MagicMock()
    controller.is_moving = True
    controller.btn_controller = MagicMock()
    controller.keyboard_controller = MagicMock()
    controller.game_config = MagicMock()
    controller.game_config.get_action_keys.return_value = {
        'move_w': 'w',
        'interact': 'f',
    }
    controller.background_mode = False
    release_flow_inputs(MagicMock(controller=controller))
    assert not controller.is_moving
    controller.btn_controller.reset.assert_called_once()
    controller.keyboard_controller.reset.assert_called_once()
    assert controller.keyboard_controller.keyboard.release.call_count == 2
    controller.keyboard_controller.mouse.release.assert_called_with(mouse.Button.left)


@pytest.mark.parametrize('hwnd', [123, None])
def test_release_background_drag_and_mouse_interaction(
    hwnd: int | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """后台拖拽按窗口状态补发松键，交互映射到鼠标也会释放。"""
    controller = MagicMock()
    controller.game_config.get_action_keys.return_value = {
        'move_w': 'w', 'interact': 'mouse_right',
    }
    controller.background_mode = True
    controller.game_win.get_hwnd.return_value = hwnd
    post_message = MagicMock()
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_run_flow.ctypes.windll.user32.PostMessageW',
        post_message,
    )
    release_flow_inputs(MagicMock(controller=controller))
    controller.keyboard_controller.keyboard.release.assert_called_once()
    controller.keyboard_controller.mouse.release.assert_any_call(mouse.Button.right)
    controller.keyboard_controller.mouse.release.assert_any_call(mouse.Button.left)
    if hwnd is None:
        post_message.assert_not_called()
    else:
        post_message.assert_called_once_with(hwnd, 0x0202, 0, 0)
