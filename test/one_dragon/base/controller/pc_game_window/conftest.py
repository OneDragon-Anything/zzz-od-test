from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.base.controller import pc_game_window as module


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """模拟桌面窗口与进程，不控制真实桌面。"""
    live: dict[int, SimpleNamespace] = {}
    processes: dict[int, Mock] = {}

    def add(title: str, hwnd: int, pid: int | None = None) -> SimpleNamespace:
        win = SimpleNamespace(title=title, _hWnd=hwnd, isActive=False)
        win.restore = Mock()
        win.activate = Mock()
        live[hwnd] = win
        pid = pid or hwnd + 100
        process = Mock(pid=pid)
        process.is_running.return_value = True
        processes[hwnd] = process
        return win

    lookup = Mock(side_effect=lambda title: [win for win in live.values() if title in win.title])
    monkeypatch.setattr(module.pyautogui, 'getWindowsWithTitle', lookup)
    monkeypatch.setattr(module.ctypes.windll.user32, 'IsWindow', lambda hwnd: hwnd in live)
    monkeypatch.setattr(module.win32process, 'GetWindowThreadProcessId',
                        lambda hwnd: (hwnd + 1000, processes[hwnd].pid))
    monkeypatch.setattr(module.psutil, 'Process',
                        lambda pid: next(p for p in processes.values() if p.pid == pid))
    game = module.PcGameWindow()
    game.update_win_titles(['绝区零', 'ZenlessZoneZero'])
    return SimpleNamespace(game=game, add=add, live=live, processes=processes, lookup=lookup)
