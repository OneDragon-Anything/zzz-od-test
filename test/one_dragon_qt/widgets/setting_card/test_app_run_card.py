import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QLabel
from qfluentwidgets import CaptionLabel

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfigItem,
)
from one_dragon_qt.widgets.setting_card.app_run_card import AppRunCard


def test_migrated_app_card_shows_yellow_marker_and_info_tooltip() -> None:
    """迁移应用卡片应显示黄色迁移标记和关闭说明。"""
    _app = QApplication.instance() or QApplication([])
    item = ApplicationGroupConfigItem(app_id='migrated_app', enabled=True)
    item.app_name = '迁移应用'

    migrated_card = AppRunCard(item, is_migrated=True)
    migrated_card.update_display()

    assert migrated_card.content_widget.titleLabel.text() == '迁移应用'
    assert migrated_card.migrated_label.text() == '已迁移'
    assert isinstance(migrated_card.migrated_label, CaptionLabel)
    assert migrated_card.migrated_label.lightColor.name() == '#b26a00'
    assert migrated_card.migrated_label.darkColor.name() == '#ffd166'
    assert migrated_card.migrated_info_btn.toolTip() == '关闭后将从一条龙列表中永久移除'
    assert isinstance(migrated_card.migrated_info_btn, QLabel)
    assert not migrated_card.migrated_info_btn.pixmap().isNull()
    assert migrated_card.migrated_info_btn.pixmap().width() == 14
    assert migrated_card.migrated_info_btn.pixmap().height() == 14
    assert migrated_card.migrated_info_btn.width() == 18
    assert migrated_card.migrated_info_btn.height() == 18
    assert migrated_card.migrated_info_btn.contentsMargins().top() == 3
    assert migrated_card.migrated_label.font().pixelSize() == 14
    title_layout = migrated_card.content_widget.vBoxLayout.itemAt(0).layout()
    assert title_layout.spacing() == 4
    assert title_layout.itemAt(1).spacerItem().sizeHint().width() == 8
    assert title_layout.itemAt(2).widget() is migrated_card.migrated_info_btn
    assert title_layout.itemAt(3).widget() is migrated_card.migrated_label
    assert not migrated_card.migrated_label.isHidden()
    assert not migrated_card.migrated_info_btn.isHidden()

    normal_card = AppRunCard(item)
    normal_card.update_display()

    assert normal_card.content_widget.titleLabel.text() == '迁移应用'
    assert normal_card.migrated_label.isHidden()
    assert normal_card.migrated_info_btn.isHidden()
