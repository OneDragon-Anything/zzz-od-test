from types import SimpleNamespace

import pytest

from one_dragon.base.controller import pc_controller_base as module
from one_dragon.base.geometry.point import Point


@pytest.mark.parametrize('press_time', [None, 0.1])
def test_foreground_press_wait_before_first_movement(
    monkeypatch: pytest.MonkeyPatch, press_time: float | None,
) -> None:
    """通过公开入口核对按下等待；省略参数时仍立即移动。"""
    events: list[tuple] = []
    controller = object.__new__(module.PcControllerBase)
    controller.background_mode = False
    controller.game_win = SimpleNamespace(game2win_pos=lambda point: point)
    monkeypatch.setattr(module.pyautogui, 'moveTo', lambda x, y: events.append(('move', x, y)))
    monkeypatch.setattr(module.pyautogui, 'mouseDown', lambda: events.append(('down',)))
    monkeypatch.setattr(module.pyautogui, 'mouseUp', lambda: events.append(('up',)))
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: events.append(('sleep', seconds)))
    monkeypatch.setattr(module.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(mouse_event=lambda *args: None)))
    if press_time is None:
        controller.drag_to(Point(30, 40), Point(10, 20), duration=0.8)
    else:
        controller.drag_to(Point(30, 40), Point(10, 20), duration=0.8, press_time=press_time)
    assert events[0] == ('move', 10, 20)
    assert events[1] == ('down',)
    if press_time is None:
        assert events[2][0] == 'move'
    else:
        assert events[2] == ('sleep', press_time)
        assert events[3][0] == 'move'
    # 按下等待额外增加，不从原有移动时长中扣除。
    assert sum(event[1] for event in events if event[0] == 'sleep') == pytest.approx(0.8 + (press_time or 0))
    assert events[-1] == ('up',)


@pytest.mark.parametrize('press_time, expected', [(None, 0.02), (0.01, 0.02), (0.1, 0.1)])
def test_background_waits_before_first_movement(
    monkeypatch: pytest.MonkeyPatch, press_time: float | None, expected: float,
) -> None:
    """后台入口传递等待参数，同时保留至少 0.02 秒的等待。"""
    events: list[tuple] = []
    controller = object.__new__(module.PcControllerBase)
    controller.background_mode = True
    controller._ensure_mouse_mode = lambda: True
    controller.game_win = SimpleNamespace(get_hwnd=lambda: 1, get_scaled_game_pos=lambda point: point)
    controller._set_cursor_to = lambda hwnd, x, y: events.append(('move', x, y))
    monkeypatch.setattr(module.win32gui, 'SendMessage', lambda *args: None)
    monkeypatch.setattr(module.win32gui, 'PostMessage', lambda hwnd, msg, *args: events.append(('message', msg)))
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: events.append(('sleep', seconds)))
    if press_time is None:
        controller.drag_to(Point(30, 40), Point(10, 20), duration=0.8)
    else:
        controller.drag_to(Point(30, 40), Point(10, 20), duration=0.8, press_time=press_time)
    down_index = events.index(('message', module.win32con.WM_LBUTTONDOWN))
    assert events[down_index + 1] == ('sleep', expected)
    assert events[down_index + 2][0] == 'move'
    assert sum(event[1] for event in events[down_index:] if event[0] == 'sleep') == pytest.approx(0.8 + expected)
    assert events[-1] == ('message', module.win32con.WM_LBUTTONUP)
