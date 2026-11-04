from types import SimpleNamespace

import pytest


def test_same_candidates_preserve_binding(windows: SimpleNamespace) -> None:
    original = windows.add('ZenlessZoneZero', 1)
    assert windows.game.get_win() is original
    titles = ['绝区零', 'ZenlessZoneZero', '绝区零']
    windows.game.update_win_titles(titles)
    titles.clear()
    assert windows.game.get_win() is original
    assert windows.game.win_titles == ('绝区零', 'ZenlessZoneZero')


def test_single_title_replaces_candidates(windows: SimpleNamespace) -> None:
    windows.add('绝区零', 1)
    windows.game.init_win()
    windows.game.update_win_title('自定义')
    assert windows.game._hWnd is None
    assert windows.game.get_win() is None
    assert windows.game.win_titles == ('自定义',)


@pytest.mark.parametrize('titles', [[], [''], ['  '], ['绝区零', '']])
def test_invalid_candidates_do_not_change_binding(windows: SimpleNamespace, titles: list[str]) -> None:
    original = windows.add('绝区零', 1)
    windows.game.init_win()
    with pytest.raises(ValueError):
        windows.game.update_win_titles(titles)
    assert windows.game.get_win() is original
