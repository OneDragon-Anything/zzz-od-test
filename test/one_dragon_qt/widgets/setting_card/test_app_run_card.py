import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfigItem,
)
from one_dragon_qt.widgets.setting_card.app_run_card import AppRunCard


def test_app_run_card_has_no_migration_marker() -> None:
    """一条龙只显示默认应用，卡片不再提供旧迁移标记。"""
    _app = QApplication.instance() or QApplication([])
    item = ApplicationGroupConfigItem(app_id='default_app', enabled=True)
    item.app_name = '默认应用'

    card = AppRunCard(item)
    card.update_display()

    assert card.content_widget.titleLabel.text() == '默认应用'
    assert not hasattr(card, 'migrated_label')
    assert not hasattr(card, 'migrated_info_btn')
