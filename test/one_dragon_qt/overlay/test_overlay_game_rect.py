"""Overlay 跟随窗口不能在界面线程查找游戏窗口（#3072 回归）。"""
import threading
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from one_dragon.base.controller import pc_game_window as pc_game_window_module
from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.window_error import WindowAmbiguousError
from one_dragon_qt.overlay.overlay_manager import OverlayManager

_TIMEOUT = 2.0


def _call_with_timeout(func: Callable[[], Any]) -> Any:
    """在独立线程里调用，超时视为被阻塞，避免测试本身卡死。"""
    result: dict[str, Any] = {}

    def run() -> None:
        result['value'] = func()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(_TIMEOUT)
    assert not thread.is_alive(), 'Overlay 调用被窗口查找阻塞'
    return result['value']


@pytest.fixture
def stuck_game(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    """未绑定的游戏窗口，后台线程的 init_win 卡在窗口枚举里。"""
    entered = threading.Event()
    release = threading.Event()

    def lookup(_title: str) -> list:
        entered.set()
        release.wait(_TIMEOUT * 5)
        return []

    lookup_mock = Mock(side_effect=lookup)
    monkeypatch.setattr(pc_game_window_module.pyautogui, 'getWindowsWithTitle', lookup_mock)
    game = PcGameWindow()
    game.update_win_titles(['绝区零', 'ZenlessZoneZero'])
    background = threading.Thread(target=game.init_win, daemon=True)
    background.start()
    assert entered.wait(_TIMEOUT)
    yield SimpleNamespace(game=game, lookup=lookup_mock)
    release.set()
    background.join(_TIMEOUT)


def _fake_manager(game: PcGameWindow) -> SimpleNamespace:
    return SimpleNamespace(
        ctx=SimpleNamespace(controller=SimpleNamespace(game_win=game)),
        _resolve_game_rect_once=OverlayManager._resolve_game_rect_once,
        _request_game_win_binding=Mock(),
    )


def test_game_rect_not_blocked_by_background_lookup(stuck_game: SimpleNamespace) -> None:
    manager = _fake_manager(stuck_game.game)
    assert _call_with_timeout(lambda: OverlayManager._get_game_rect(manager)) is None
    # 未绑定时交给后台查找，界面线程自己不枚举窗口
    manager._request_game_win_binding.assert_called_once_with(stuck_game.game)
    assert stuck_game.lookup.call_count == 1


def test_window_active_not_blocked_by_background_lookup(stuck_game: SimpleNamespace) -> None:
    manager = _fake_manager(stuck_game.game)
    assert _call_with_timeout(lambda: OverlayManager._is_game_window_active(manager)) is False
    assert stuck_game.lookup.call_count == 1


def test_game_rect_never_uses_discovering_api() -> None:
    game_win = Mock(spec=['peek_hwnd', 'peek_win', 'peek_win_rect', 'init_win',
                          'refresh_win', 'get_win', 'get_hwnd', 'is_win_valid', 'win_rect'])
    game_win.peek_hwnd.return_value = None
    manager = _fake_manager(game_win)
    assert OverlayManager._get_game_rect(manager) is None
    game_win.refresh_win.assert_not_called()
    game_win.init_win.assert_not_called()
    game_win.get_win.assert_not_called()
    game_win.get_hwnd.assert_not_called()


def test_background_binding_runs_once_at_a_time() -> None:
    release = threading.Event()
    started = threading.Event()

    def init_win() -> None:
        started.set()
        release.wait(_TIMEOUT * 5)
        raise WindowAmbiguousError('找到多个窗口')

    game_win = SimpleNamespace(init_win=Mock(side_effect=init_win))
    manager = SimpleNamespace(_bind_thread=None, _last_bind_request_time=0.0)
    OverlayManager._request_game_win_binding(manager, game_win)
    assert started.wait(_TIMEOUT)
    manager._last_bind_request_time = 0.0  # 排除频率限制，只验证不会并发查找
    OverlayManager._request_game_win_binding(manager, game_win)
    assert game_win.init_win.call_count == 1
    release.set()
    manager._bind_thread.join(_TIMEOUT)
    # 后台查找的异常不外抛到线程之外
    assert not manager._bind_thread.is_alive()
