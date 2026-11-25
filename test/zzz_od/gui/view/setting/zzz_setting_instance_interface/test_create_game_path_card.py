from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QApplication

from one_dragon_qt.view.setting.setting_instance_interface import (
    SettingInstanceInterface,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from zzz_od.gui.view.setting.zzz_setting_instance_interface import (
    ZSettingInstanceInterface,
)


def test_project_card_has_two_working_buttons() -> None:
    app = QApplication.instance() or QApplication([])
    page = ZSettingInstanceInterface(ctx=SimpleNamespace())
    page._on_game_path_clicked = Mock()
    page._read_game_path = Mock()
    card = page._create_game_path_card()
    assert isinstance(card, MultiPushSettingCard)
    buttons = [card.btn_layout.itemAt(index).widget() for index in range(card.btn_layout.count())
               if card.btn_layout.itemAt(index).widget() is not None]
    assert len(buttons) == 2
    buttons[0].click()
    buttons[1].click()
    page._on_game_path_clicked.assert_called_once()
    page._read_game_path.assert_called_once()
    card.setContent('C:/Game/ZenlessZoneZero.exe')
    assert card.contentLabel.text() == 'C:/Game/ZenlessZoneZero.exe'
    page.close()
    app.processEvents()


def test_base_card_keeps_manual_selection_only() -> None:
    app = QApplication.instance() or QApplication([])
    page = SettingInstanceInterface(ctx=SimpleNamespace())
    page._on_game_path_clicked = Mock()
    card = page._create_game_path_card()
    assert isinstance(card, PushSettingCard)
    card.button.click()
    page._on_game_path_clicked.assert_called_once()
    page.close()
    app.processEvents()
