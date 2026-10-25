from unittest.mock import Mock

import pytest

from one_dragon.base.controller import pc_controller_base as module
from one_dragon.base.controller.window_error import WindowAmbiguousError


def test_controller_and_screenshot_strategies_share_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, 'KeyboardMouseController', Mock())
    controller = module.PcControllerBase(screenshot_method='auto')
    controller.set_window_titles(['A', 'B'])
    assert controller.game_win.win_titles == ('A', 'B')
    assert controller.screenshot_controller.game_win is controller.game_win
    for strategy in controller.screenshot_controller.strategies.values():
        assert strategy.game_win is controller.game_win
    controller.set_window_title('C')
    assert controller.game_win.win_titles == ('C',)


def test_ambiguous_window_blocks_run_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, 'KeyboardMouseController', Mock())
    controller = module.PcControllerBase(screenshot_method='auto')
    controller.game_win.init_win = Mock(side_effect=WindowAmbiguousError('多个游戏窗口'))
    controller.game_win.active = Mock()
    assert not controller.init_before_context_run()
    controller.game_win.active.assert_not_called()
