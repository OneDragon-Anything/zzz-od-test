from types import SimpleNamespace

import pytest

from one_dragon.base.controller import pc_controller_base as module
from one_dragon.base.geometry.point import Point


@pytest.mark.parametrize('duration, movement_time', [(None, 0.1), (0.8, 0.3), (0.2, 0.1)])
def test_foreground_press_wait_before_first_movement(
    monkeypatch: pytest.MonkeyPatch, duration: float | None, movement_time: float,
) -> None:
    """前台固定按住 0.3 秒，移动时间扣除前后停顿且不少于 0.1 秒。"""
    events: list[tuple] = []
    controller = object.__new__(module.PcControllerBase)
    controller.background_mode = False
    controller.game_win = SimpleNamespace(game2win_pos=lambda point: point)
    monkeypatch.setattr(module.pyautogui, 'moveTo', lambda x, y: events.append(('move', x, y)))
    monkeypatch.setattr(module.pyautogui, 'mouseDown', lambda: events.append(('down',)))
    monkeypatch.setattr(module.pyautogui, 'mouseUp', lambda: events.append(('up',)))
    monkeypatch.setattr(module, 'time', SimpleNamespace(sleep=lambda seconds: events.append(('sleep', seconds))))
    monkeypatch.setattr(module.ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(mouse_event=lambda *args: None)))
    if duration is None:
        controller.drag_to(Point(30, 40), Point(10, 20))
    else:
        controller.drag_to(Point(30, 40), Point(10, 20), duration=duration)
    assert events[:3] == [('move', 10, 20), ('down',), ('sleep', 0.3)]
    assert events[3][0] == 'move'
    assert [event for event in events if event[0] == 'move'][-1] == ('move', 30, 40)
    assert events[-2:] == [('sleep', 0.2), ('up',)]
    sleeps = [event[1] for event in events if event[0] == 'sleep']
    assert sum(sleeps[1:-1]) == pytest.approx(movement_time)
    assert sum(sleeps) == pytest.approx(0.3 + movement_time + 0.2)


def test_background_waits_before_first_movement(monkeypatch: pytest.MonkeyPatch) -> None:
    """后台保持按下后等待 0.02 秒，移动时间只扣除终点停顿。"""
    events: list[tuple] = []
    controller = object.__new__(module.PcControllerBase)
    controller.background_mode = True
    controller._ensure_mouse_mode = lambda: True
    controller.game_win = SimpleNamespace(get_hwnd=lambda: 1, get_scaled_game_pos=lambda point: point)
    controller._set_cursor_to = lambda hwnd, x, y: events.append(('move', x, y))
    monkeypatch.setattr(module.win32gui, 'SendMessage', lambda *args: None)
    monkeypatch.setattr(module.win32gui, 'PostMessage', lambda hwnd, msg, *args: events.append(('message', msg)))
    monkeypatch.setattr(module, 'time', SimpleNamespace(sleep=lambda seconds: events.append(('sleep', seconds))))
    controller.drag_to(Point(30, 40), Point(10, 20), duration=0.8)
    down_index = events.index(('message', module.win32con.WM_LBUTTONDOWN))
    assert events[down_index + 1] == ('sleep', 0.02)
    assert events[down_index + 2][0] == 'move'
    assert [event for event in events if event[0] == 'move'][-1] == ('move', 30, 40)
    sleeps = [event[1] for event in events[down_index:] if event[0] == 'sleep']
    assert sum(sleeps[1:-1]) == pytest.approx(0.6)
    assert sum(sleeps) == pytest.approx(0.82)
    assert events[-2:] == [('sleep', 0.2), ('message', module.win32con.WM_LBUTTONUP)]
