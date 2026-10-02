"""覆盖真实前台点击入口的窗口归属及恢复行为。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.base.controller import owned_foreground_click as ownership
from one_dragon.base.controller import pc_controller_base as controller_module
from one_dragon.base.geometry.point import Point


@pytest.fixture
def click_fixture(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """构造无游戏和鼠标副作用的真实控制器入口。"""
    state = SimpleNamespace(
        hwnd=42, foreground=42, pixel=42, exists=True, identity=(7, 8), topmost=False
    )
    calls: list[int] = []

    def set_position(hwnd: int, insert_after: int, *args: int) -> None:
        """记录并模拟置顶后的像素归属。"""
        calls.append(insert_after)
        if insert_after == ownership.win32con.HWND_TOPMOST:
            state.pixel = hwnd

    def activate() -> bool:
        """模拟官方窗口激活。"""
        state.foreground = state.hwnd
        return True

    monkeypatch.setattr(ownership.win32gui, 'IsWindow', lambda hwnd: state.exists)
    monkeypatch.setattr(
        ownership.win32gui, 'GetWindowRect', lambda hwnd: (0, 0, 1920, 1080)
    )
    monkeypatch.setattr(
        ownership.win32gui, 'GetForegroundWindow', lambda: state.foreground
    )
    monkeypatch.setattr(
        ownership.win32gui, 'WindowFromPoint', lambda point: state.pixel
    )
    monkeypatch.setattr(ownership.win32gui, 'GetAncestor', lambda hwnd, flag: hwnd)
    monkeypatch.setattr(
        ownership.win32gui,
        'GetWindowLong',
        lambda hwnd, flag: ownership.win32con.WS_EX_TOPMOST if state.topmost else 0,
    )
    monkeypatch.setattr(ownership.win32gui, 'SetWindowPos', set_position)
    monkeypatch.setattr(
        ownership.win32process, 'GetWindowThreadProcessId', lambda hwnd: state.identity
    )
    move, down, up = Mock(), Mock(), Mock()
    monkeypatch.setattr(controller_module.pyautogui, 'moveTo', move)
    monkeypatch.setattr(controller_module.pyautogui, 'mouseDown', down)
    monkeypatch.setattr(controller_module.pyautogui, 'mouseUp', up)
    monkeypatch.setattr(controller_module.time, 'sleep', lambda seconds: None)
    controller = object.__new__(controller_module.PcControllerBase)
    controller.game_win = SimpleNamespace(
        get_hwnd=lambda: state.hwnd, game2win_pos=lambda point: point, active=activate
    )
    keyboard = SimpleNamespace(press=Mock(), release=Mock())
    controller.keyboard_controller = SimpleNamespace(keyboard=keyboard)
    return SimpleNamespace(
        state=state,
        calls=calls,
        controller=controller,
        move=move,
        down=down,
        up=up,
        keyboard=keyboard,
    )


def test_uncovered_click_preserves_z_order(click_fixture: SimpleNamespace) -> None:
    """无遮挡时沿用原有点击且不改变置顶属性。"""
    assert click_fixture.controller._foreground_click(Point(960, 540))
    click_fixture.down.assert_called_once()
    click_fixture.up.assert_called_once()
    assert click_fixture.calls == []


def test_covered_click_borrows_and_restores_topmost(
    click_fixture: SimpleNamespace,
) -> None:
    """浏览器遮挡时只临时提升绑定游戏窗口。"""
    click_fixture.state.foreground = click_fixture.state.pixel = 99
    assert click_fixture.controller._foreground_click(Point(960, 540))
    assert click_fixture.calls == [
        ownership.win32con.HWND_TOPMOST,
        ownership.win32con.HWND_NOTOPMOST,
    ]
    click_fixture.down.assert_called_once()


def test_focus_stolen_after_move_does_not_press(click_fixture: SimpleNamespace) -> None:
    """鼠标移动后焦点被抢走则不发送按钮输入。"""
    click_fixture.move.side_effect = lambda *args: setattr(
        click_fixture.state, 'foreground', 99
    )
    assert not click_fixture.controller._foreground_click(Point(960, 540))
    click_fixture.down.assert_not_called()
    click_fixture.up.assert_not_called()


def test_pixel_covered_after_move_does_not_press(
    click_fixture: SimpleNamespace,
) -> None:
    """移动后点击点被其他窗口遮挡则拒绝输入。"""
    click_fixture.move.side_effect = lambda *args: setattr(
        click_fixture.state, 'pixel', 99
    )
    assert not click_fixture.controller._foreground_click(Point(960, 540))
    click_fixture.down.assert_not_called()


def test_existing_topmost_is_preserved(click_fixture: SimpleNamespace) -> None:
    """用户原有置顶窗口不被降级。"""
    click_fixture.state.topmost = True
    click_fixture.state.foreground = 99
    assert click_fixture.controller._foreground_click(Point(960, 540))
    assert click_fixture.calls == []


def test_window_destroyed_during_click_skips_restore(
    click_fixture: SimpleNamespace,
) -> None:
    """点击触发窗口销毁时不恢复失效句柄。"""
    click_fixture.state.pixel = 99
    click_fixture.down.side_effect = lambda **kwargs: setattr(
        click_fixture.state, 'exists', False
    )
    assert click_fixture.controller._foreground_click(Point(960, 540))
    assert click_fixture.calls == [ownership.win32con.HWND_TOPMOST]


def test_reused_handle_does_not_press_or_restore(
    click_fixture: SimpleNamespace,
) -> None:
    """窗口句柄复用时不向新进程输入或修改其置顶。"""
    click_fixture.state.pixel = 99
    click_fixture.move.side_effect = lambda *args: setattr(
        click_fixture.state, 'identity', (70, 80)
    )
    assert not click_fixture.controller._foreground_click(Point(960, 540))
    click_fixture.down.assert_not_called()
    assert click_fixture.calls == [ownership.win32con.HWND_TOPMOST]


def test_input_exception_releases_alt_and_mouse(click_fixture: SimpleNamespace) -> None:
    """输入异常仍释放按键、鼠标，并恢复置顶。"""
    click_fixture.state.pixel = 99
    click_fixture.down.side_effect = RuntimeError('input fixture')
    with pytest.raises(RuntimeError, match='input fixture'):
        click_fixture.controller._foreground_click(Point(960, 540), pc_alt=True)
    click_fixture.up.assert_called_once()
    click_fixture.keyboard.release.assert_called_once()
    assert click_fixture.calls[-1] == ownership.win32con.HWND_NOTOPMOST


@pytest.mark.parametrize('hwnd', [None, 0])
def test_missing_window_does_not_input(
    click_fixture: SimpleNamespace, hwnd: int | None
) -> None:
    """缺失窗口时不得移动鼠标或发送按键。"""
    click_fixture.state.hwnd = hwnd
    assert not click_fixture.controller._foreground_click(Point(960, 540))
    click_fixture.move.assert_not_called()


def test_outside_point_does_not_raise_window(click_fixture: SimpleNamespace) -> None:
    """窗口范围外的当前鼠标坐标不触发置顶或点击。"""
    assert not click_fixture.controller._foreground_click(Point(2000, 1100))
    click_fixture.move.assert_not_called()
    assert click_fixture.calls == []
