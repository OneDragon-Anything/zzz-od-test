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


def test_new_app_with_run_record_shows_unused_text() -> None:
    """一条龙新应用带运行记录时也要显示“还没使用过”，不能只说上次运行时间。"""
    _app = QApplication.instance() or QApplication([])
    item = ApplicationGroupConfigItem(app_id='new_app', enabled=False, is_persisted=False)
    item.app_name = '新应用'
    card = AppRunCard(item)
    from types import SimpleNamespace

    card.run_record = SimpleNamespace(run_time='2026-01-01 00:00:00')
    card.update_display()

    assert card.content_widget.titleLabel.text() == '【New！】新应用'
    assert card.content_widget.contentLabel.text() == '新功能 还没使用过'
