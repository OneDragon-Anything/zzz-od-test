"""窗口查找卡住时，只读接口和其他线程不能被拖住（#3072 回归）。"""
import threading
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import call

import pytest

_TIMEOUT = 2.0


def _call_with_timeout(func: Callable[[], Any]) -> Any:
    """在独立线程里调用，超时视为被阻塞，避免测试本身卡死。"""
    result: dict[str, Any] = {}

    def run() -> None:
        result['value'] = func()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(_TIMEOUT)
    assert not thread.is_alive(), '调用被窗口查找阻塞'
    return result['value']


class _BlockedLookup:
    """让后台线程的第一次窗口枚举卡住，直到测试放行；其他枚举正常返回。"""

    def __init__(self, windows: SimpleNamespace) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.first_result: list[SimpleNamespace] | None = None
        self._normal = windows.lookup.side_effect
        self._first = True
        windows.lookup.side_effect = self._lookup
        self.thread = threading.Thread(target=windows.game.init_win, daemon=True)

    def _lookup(self, title: str) -> list[SimpleNamespace]:
        if self._first:
            self._first = False
            self.entered.set()
            self.release.wait(_TIMEOUT * 5)
            if self.first_result is not None:
                return self.first_result
        return self._normal(title)

    def start(self) -> None:
        """启动后台 init_win，并等它卡在枚举里。"""
        self.thread.start()
        assert self.entered.wait(_TIMEOUT)

    def finish(self) -> None:
        """放行枚举并等后台 init_win 结束。"""
        self.release.set()
        self.thread.join(_TIMEOUT)
        assert not self.thread.is_alive()


@pytest.fixture
def blocked(windows: SimpleNamespace) -> Iterator[_BlockedLookup]:
    lookup = _BlockedLookup(windows)
    yield lookup
    lookup.release.set()
    if lookup.thread.is_alive():
        lookup.thread.join(_TIMEOUT)


def test_peek_not_blocked_by_enumeration(windows: SimpleNamespace, blocked: _BlockedLookup) -> None:
    blocked.start()
    game = windows.game
    assert _call_with_timeout(game.peek_hwnd) is None
    assert _call_with_timeout(game.peek_win) is None
    assert _call_with_timeout(game.peek_win_rect) is None
    assert _call_with_timeout(lambda: game.is_bound_valid) is False
    assert _call_with_timeout(lambda: game.bound_win_title) is None
    # 只读接口不触发新的窗口枚举
    assert windows.lookup.call_count == 1


def test_other_threads_not_blocked_by_enumeration(windows: SimpleNamespace, blocked: _BlockedLookup) -> None:
    windows.add('绝区零', 1)
    blocked.start()
    game = windows.game
    # 另一个线程查找、核验、修改候选标题都不需要等卡住的查找结束
    assert _call_with_timeout(game.get_hwnd) == 1
    assert _call_with_timeout(lambda: game.is_win_valid) is True
    assert _call_with_timeout(game.peek_hwnd) == 1
    _call_with_timeout(lambda: game.update_win_titles(['绝区零', 'ZenlessZoneZero']))


def test_existing_binding_wins_over_late_result(windows: SimpleNamespace, blocked: _BlockedLookup) -> None:
    windows.add('绝区零', 1)
    windows.add('ZenlessZoneZero', 2)
    blocked.first_result = []  # 后台线程枚举首选标题时窗口 1 还没出现
    blocked.start()
    assert _call_with_timeout(windows.game.get_hwnd) == 1
    blocked.finish()
    # 后台线程随后找到了窗口 2，但不能抢走已建立的有效绑定
    assert call('ZenlessZoneZero') in windows.lookup.call_args_list
    assert windows.game.peek_hwnd() == 1


def test_titles_changed_during_enumeration_discards_result(windows: SimpleNamespace,
                                                           blocked: _BlockedLookup) -> None:
    windows.add('绝区零', 1)
    blocked.start()
    _call_with_timeout(lambda: windows.game.update_win_titles(['自定义标题']))
    blocked.finish()
    assert windows.game.peek_hwnd() is None
    assert windows.game._hWnd is None


def test_peek_releases_invalid_binding_without_enumeration(windows: SimpleNamespace) -> None:
    windows.add('绝区零', 1)
    windows.add('ZenlessZoneZero', 2)
    assert windows.game.get_hwnd() == 1
    windows.lookup.reset_mock()
    windows.live.pop(1)
    assert windows.game.peek_hwnd() is None
    assert windows.game._hWnd is None
    windows.lookup.assert_not_called()


def test_peek_keeps_valid_binding(windows: SimpleNamespace) -> None:
    original = windows.add('绝区零', 1)
    windows.game.init_win()
    windows.lookup.reset_mock()
    assert windows.game.peek_win() is original
    assert windows.game.peek_hwnd() == 1
    assert windows.game.is_bound_valid
    assert windows.game.bound_win_title == '绝区零'
    windows.lookup.assert_not_called()
