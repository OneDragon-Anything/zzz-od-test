"""使用 Qt 离屏界面验证机械硬盘开关、配置保存和实例切换。"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from zzz_od.config.game_config import GameConfig
from zzz_od.gui.view.setting.setting_game_interface import SettingGameInterface


def make_config(data: dict | None = None) -> GameConfig:
    """构造只在内存中保存的游戏配置。"""
    config = GameConfig.__new__(GameConfig)
    config.data = {} if data is None else data.copy()
    config.save = MagicMock()
    return config


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Iterator[QApplication]:
    """保留 Qt 应用引用，离屏运行不打开用户桌面窗口。"""
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


def flush_events(app: QApplication) -> None:
    """完成配置适配器的异步读取与控件更新。"""
    for _ in range(4):
        app.processEvents()


def test_hdd_settings_save_and_switch_instance(app: QApplication) -> None:
    """默认禁用上限，开关启用后保存设置，切换账号读取新配置。"""
    ctx = MagicMock()
    first_config = make_config()
    ctx.game_config = first_config
    interface = SettingGameInterface(ctx)
    interface.on_interface_shown()
    flush_events(app)
    assert interface.hdd_mode_switch.btn.isChecked() is False
    assert interface.hdd_battle_loading_timeout_opt.isEnabled() is False
    spin = interface.hdd_battle_loading_timeout_opt.spin_box
    assert (spin.minimum(), spin.maximum(), spin.value()) == (60, 600, 180)
    assert first_config.data == {}

    interface.hdd_mode_switch.btn.setChecked(True)
    assert interface.hdd_battle_loading_timeout_opt.isEnabled() is True
    spin.setValue(240)
    assert first_config.hdd_mode is True
    assert first_config.hdd_battle_loading_timeout == 240

    second_config = make_config({'hdd_battle_loading_timeout': 300})
    ctx.game_config = second_config
    interface.on_interface_shown()
    flush_events(app)
    assert spin.value() == 300
    assert interface.hdd_mode_switch.btn.isChecked() is False
    assert interface.hdd_battle_loading_timeout_opt.isEnabled() is False
    assert first_config.hdd_battle_loading_timeout == 240
    assert second_config.hdd_mode is False
    interface.deleteLater()
