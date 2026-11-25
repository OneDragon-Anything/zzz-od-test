from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from one_dragon.base.controller.window_error import WindowAmbiguousError
from one_dragon_qt.view.setting.setting_instance_interface import (
    SettingInstanceInterface,
)
from zzz_od.gui.view.setting import zzz_setting_instance_interface as module


@pytest.mark.parametrize('error', [None, FileNotFoundError('未找到窗口'),
                                  psutil.AccessDenied(1), psutil.NoSuchProcess(1),
                                  WindowAmbiguousError('多个同标题窗口')])
def test_read_preserves_old_path_on_failure(monkeypatch: pytest.MonkeyPatch, error: Exception | None) -> None:
    account = SimpleNamespace(game_path='old.exe')
    other_account = SimpleNamespace(game_path='other.exe')
    window = Mock()
    window.get_executable_path.return_value = 'C:/Game/ZenlessZoneZero.exe'
    window.get_executable_path.side_effect = error
    ctx = SimpleNamespace(controller=SimpleNamespace(game_win=window), game_account_config=account)
    page = SimpleNamespace(ctx=ctx, game_path_opt=Mock())
    page._on_game_path_chosen = lambda path: SettingInstanceInterface._on_game_path_chosen(page, path)
    success, warning = Mock(), Mock()
    monkeypatch.setattr(module.InfoBar, 'success', success)
    monkeypatch.setattr(module.InfoBar, 'warning', warning)
    module.ZSettingInstanceInterface._read_game_path(page)
    if error is None:
        assert account.game_path == 'C:/Game/ZenlessZoneZero.exe'
        page.game_path_opt.setContent.assert_called_once_with(account.game_path)
        success.assert_called_once()
        warning.assert_not_called()
    else:
        assert account.game_path == 'old.exe'
        page.game_path_opt.setContent.assert_not_called()
        success.assert_not_called()
        warning.assert_called_once()
    assert other_account.game_path == 'other.exe'
    window.active.assert_not_called()


def test_region_change_does_not_reinitialize_controller() -> None:
    page = SimpleNamespace(ctx=Mock(), set_ui_of_game_region=Mock())
    module.ZSettingInstanceInterface.on_game_region_opt_changed(page, 0, 'us')
    page.set_ui_of_game_region.assert_called_once_with('us')
    page.ctx.init_controller.assert_not_called()
