import pytest

from one_dragon.base.controller import pc_controller_base
from one_dragon.base.geometry.point import Point


def test_win_scroll_uses_raw_wheel_clicks(monkeypatch: pytest.MonkeyPatch) -> None:
    move_calls: list[tuple[int, int]] = []
    scroll_calls: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        pc_controller_base.pyautogui,
        'moveTo',
        lambda x, y: move_calls.append((x, y)),
    )
    monkeypatch.setattr(
        pc_controller_base.pyautogui,
        'scroll',
        lambda clicks, x, y: scroll_calls.append((clicks, x, y)),
    )

    pc_controller_base.win_scroll(300, Point(100, 200))

    assert move_calls == [(100, 200)]
    assert scroll_calls == [(-300, 100, 200)]
