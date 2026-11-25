from types import SimpleNamespace

import pytest

from one_dragon.base.controller.window_error import WindowAmbiguousError


def test_candidates_use_exact_titles_and_priority(windows: SimpleNamespace) -> None:
    windows.add('绝区零 - 文档', 1)
    intl = windows.add('ZenlessZoneZero', 2)
    assert windows.game.get_win() is intl
    windows.add('绝区零', 3)
    windows.game.init_win()
    windows.game.refresh_win()
    assert windows.game.get_hwnd() == 2
    assert windows.game.win_title == '绝区零'
    assert windows.game.bound_win_title == 'ZenlessZoneZero'


def test_first_binding_uses_priority(windows: SimpleNamespace) -> None:
    windows.add('ZenlessZoneZero', 1)
    windows.add('绝区零', 2)
    assert windows.game.get_hwnd() == 2


def test_same_title_is_ambiguous(windows: SimpleNamespace) -> None:
    windows.add('绝区零', 1)
    windows.add('绝区零', 2)
    with pytest.raises(WindowAmbiguousError, match='多个'):
        windows.game.init_win()
    assert windows.game._hWnd is None


def test_valid_binding_ignores_new_same_title_window(windows: SimpleNamespace) -> None:
    original = windows.add('绝区零', 1)
    assert windows.game.get_win() is original
    windows.add('绝区零', 2)
    assert windows.game.get_win() is original


def test_closed_window_rebinds(windows: SimpleNamespace) -> None:
    windows.add('绝区零', 1)
    windows.add('ZenlessZoneZero', 2)
    assert windows.game.get_hwnd() == 1
    windows.live.pop(1)
    assert windows.game.get_hwnd() == 2
    windows.live.clear()
    assert windows.game.get_win() is None
    assert windows.game._process is None
    assert windows.game.bound_win_title is None


def test_process_reuse_invalidates_binding(windows: SimpleNamespace) -> None:
    windows.add('绝区零', 1)
    windows.game.init_win()
    original_process = windows.processes[1]
    original_process.is_running.return_value = False
    assert windows.game.bound_win_title is None
    windows.live.clear()
    assert windows.game.get_hwnd() is None


def test_empty_desktop_is_not_ambiguous(windows: SimpleNamespace) -> None:
    assert windows.game.get_hwnd() is None
    assert not windows.game.is_win_valid
