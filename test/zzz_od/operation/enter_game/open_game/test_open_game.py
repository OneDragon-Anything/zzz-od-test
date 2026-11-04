from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from one_dragon.base.controller.window_error import WindowAmbiguousError
from zzz_od.operation.enter_game import open_game as module


def test_existing_window_does_not_launch_or_touch_hdr() -> None:
    controller = Mock()
    controller.is_game_window_ready = True
    operation = module.OpenGame(SimpleNamespace(controller=controller))
    with patch.object(module, 'DisableAutoHDR') as disable, \
            patch.object(module, 'EnableAutoHDR') as enable, \
            patch.object(module.subprocess, 'Popen') as launch:
        assert operation.open_game().is_success
        assert operation.wait_game().is_success
        disable.assert_not_called()
        enable.assert_not_called()
        launch.assert_not_called()


def test_ambiguity_before_startup_has_no_side_effects() -> None:
    class Controller:
        @property
        def is_game_window_ready(self) -> bool:
            raise WindowAmbiguousError('多个窗口')

    operation = module.OpenGame(SimpleNamespace(controller=Controller()))
    with patch.object(module, 'DisableAutoHDR') as disable, \
            patch.object(module.subprocess, 'Popen') as launch:
        with pytest.raises(WindowAmbiguousError):
            operation.open_game()
        disable.assert_not_called()
        launch.assert_not_called()


def test_new_launch_restores_only_current_hdr_change() -> None:
    controller = Mock()
    controller.is_game_window_ready = False
    ctx = SimpleNamespace(controller=controller,
                          game_account_config=SimpleNamespace(game_path='C:/Game/game.exe'),
                          game_config=SimpleNamespace(launch_argument=False))
    operation = module.OpenGame(ctx)
    operation.round_success = Mock(return_value=SimpleNamespace(is_success=True))
    with patch.object(module, 'DisableAutoHDR') as disable, \
            patch.object(module, 'EnableAutoHDR') as enable, \
            patch.object(module.subprocess, 'Popen') as launch:
        disable.return_value.execute.return_value.success = True
        operation.open_game()
        launch.assert_called_once()
        controller.is_game_window_ready = True
        operation.wait_game()
        operation.wait_game()
        enable.assert_called_once()
