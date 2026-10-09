import os
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon_qt.services.app_setting.app_setting_manager import AppSettingManager
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.fast_scroll_area import FastScrollArea
from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.application.bagel import bagel_const, bagel_usage
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.gui.app_setting.bagel_setting_interface import BagelSettingInterface


@pytest.fixture(scope='module')
def qapp() -> QApplication:
    """创建不操作桌面的 Qt 实例。"""
    return QApplication.instance() or QApplication([])


class SettingsNavigator(PivotNavigatorInterface):
    """用真实页面栈承载设置页，省去游戏初始化。"""

    def create_sub_interface(self) -> None:
        """建立与运行页相同的二级页面入口。"""
        self.root = BaseInterface('test_run', '运行', '')
        self.add_sub_interface(self.root, enable_page_stack=True)


def test_settings_navigation_and_scrolling(
    qapp: QApplication, config: BagelConfig,
) -> None:
    """设置占用主内容区，可滚动到底部并通过统一导航返回。"""
    ctx = MagicMock()
    ctx.current_instance_idx = 99
    ctx.run_context.get_config.return_value = config
    ctx.factory_manager = ApplicationFactoryManager(
        ctx, [(Path(bagel_const.__file__).parent, PluginSource.BUILTIN)],
    )
    ctx.factory_manager.discover_factories()
    manager = AppSettingManager(ctx)
    manager.discover()
    assert manager.settable_app_ids == {'bagel'}
    navigator = SettingsNavigator('test_nav', '设置', '')
    navigator.resize(1000, 280)
    navigator.show()
    try:
        manager.show_app_setting('bagel', navigator.root, 'standalone', navigator.root)
        qapp.processEvents()
        qapp.processEvents()
        view = navigator.findChild(BagelSettingInterface)
        assert view is not None
        assert not view.isWindow()
        view.clean_mode_card.combo_box.setCurrentIndex(1)
        for _ in range(5):
            qapp.processEvents()
        scroll = view.findChild(FastScrollArea)
        assert scroll is not None
        bar = scroll.verticalScrollBar()
        assert bar.maximum() > 0
        visible_bar = scroll.scrollDelagate.vScrollBar
        start = visible_bar.handle.geometry().center()
        end = QPoint(start.x(), visible_bar.height() - 20)
        QTest.mousePress(visible_bar, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(visible_bar, end)
        QTest.mouseRelease(visible_bar, Qt.MouseButton.LeftButton, pos=end)
        qapp.processEvents()
        assert bar.value() > 0
        bar.setValue(bar.maximum())
        qapp.processEvents()
        assert not hasattr(view, 'route_editor_button')
        bottom = view.clean_qualities_card.mapTo(
            scroll.viewport(), view.clean_qualities_card.rect().bottomLeft(),
        )
        assert scroll.viewport().rect().contains(bottom)
        old_width = view.width()
        navigator.resize(1200, 600)
        qapp.processEvents()
        assert view.width() > old_width
        navigator.move(navigator.pos() + QPoint(40, 40))
        assert view.window() is navigator
        navigator.pop_setting_interface()
        assert navigator.isVisible()
        assert not navigator.stacked_widget.currentWidget().is_secondary_shown
        # 缓存页再次打开时必须按新的应用组重新绑定配置。
        ctx.run_context.get_config.reset_mock()
        manager.show_app_setting('bagel', navigator.root, 'another_group', navigator.root)
        qapp.processEvents()
        ctx.run_context.get_config.assert_called_once_with(
            app_id='bagel', instance_idx=99, group_id='another_group',
        )
    finally:
        navigator.close()


def test_settings_rebind_updates_selection_description(
    qapp: QApplication, config: BagelConfig,
) -> None:
    """重新绑定应用组时同步选择说明，载入本身不写配置。"""
    ctx = MagicMock(current_instance_idx=99)
    ctx.run_context.get_config.return_value = config
    view = BagelSettingInterface(ctx)
    view.group_id = 'standalone'
    view.on_interface_shown()
    qapp.processEvents()
    qapp.processEvents()
    other = BagelConfig(99, 'another_group')
    other.max_failure_retries = 7
    other.auto_clean_warehouse = False
    other.clean_mode = 'custom'
    other.clean_types = ['装备', '贵重物品']
    other.clean_qualities = ['S', 'Z']
    before = Path(other.file_path).read_bytes()
    ctx.run_context.get_config.return_value = other
    view.group_id = 'another_group'
    view.on_interface_shown()
    qapp.processEvents()
    qapp.processEvents()
    try:
        assert view.sale_title.text() == '已关闭自动出售'
        assert view.failure_retries_card.spin_box.value() == 7
        assert set(view.clean_types_card.get_value()) == {'装备', '贵重物品'}
        assert view.clean_types_card.contentLabel.text() == '已选 2 项'
        assert view.clean_qualities_card.contentLabel.text() == '已选 2 项'
        assert Path(other.file_path).read_bytes() == before
    finally:
        view.close()


def test_settings_save_and_show_relevant_options(qapp: QApplication, config: BagelConfig) -> None:
    """简洁列表自动保存，仅按清理状态展开方案和自定义选项。"""
    ctx = MagicMock()
    ctx.current_instance_idx = 99
    ctx.run_context.get_config.return_value = config
    view = BagelSettingInterface(ctx)
    view.group_id = 'standalone'
    view.on_interface_shown()
    view.show()
    qapp.processEvents()
    qapp.processEvents()
    assert view.failure_retries_card.spin_box.value() == 5
    assert view.failure_retries_card.spin_box.minimum() == 0
    assert view.failure_retries_card.spin_box.maximum() == 100
    assert view.failure_retries_card.titleLabel.text() == '整体重试次数'
    view.failure_retries_card.spin_box.setValue(100)
    assert BagelConfig(99, 'standalone').max_failure_retries == 100
    assert view.success_rounds_card.spin_box.value() == 1
    assert view.success_rounds_card.spin_box.minimum() == 0
    assert view.success_rounds_card.titleLabel.text() == '成功次数'
    assert view.success_rounds_card.contentLabel.text() == bagel_usage.SUCCESS_HINT
    assert view.auto_clean_switch.titleLabel.text() == '清理仓库'
    assert view.auto_clean_switch.contentLabel.text() == bagel_usage.CLEAN_SWITCH_HINT
    assert view.clean_mode_card.titleLabel.text() == '出售方案'
    assert view.clean_mode_card.default_content == bagel_usage.DEFAULT_SALE_HINT
    assert view.clean_mode_card.contentLabel.text() == bagel_usage.DEFAULT_SALE_HINT
    assert not hasattr(view, 'targets_edit')
    assert view.auto_clean_switch.btn.isChecked()
    assert not view.clean_mode_card.isHidden()
    assert not view.clean_types_card.isVisible()
    assert not view.clean_qualities_card.isVisible()
    view.success_rounds_card.spin_box.setValue(0)
    assert BagelConfig(99, 'standalone').max_success_rounds == 0
    view.clean_mode_card.combo_box.setCurrentIndex(1)
    assert not view.sale_validation.isHidden()
    assert view.clean_mode_card.contentLabel.text() == bagel_usage.CUSTOM_SALE_HINT
    assert BagelConfig(99, 'standalone').clean_mode == 'custom'
    assert not view.clean_types_card.isHidden()
    assert not view.clean_qualities_card.isHidden()
    view.clean_types_card.set_value(['装备'])
    view.clean_qualities_card.set_value(['Z'])
    view.clean_types_card._on_selection_changed(['装备'])
    view.clean_qualities_card._on_selection_changed(['Z'])
    assert BagelConfig(99, 'standalone').clean_filter_areas() == ('筛选-装备', '筛选-Z')
    view.auto_clean_switch.btn.setChecked(False)
    assert BagelConfig(99, 'standalone').auto_clean_warehouse is False
    assert view.sale_title.text() == '已关闭自动出售'
    assert view.sale_hint.text() == bagel_usage.NO_CLEAN_HINT
    assert not view.usage_card.isHidden()
    assert view.sale_validation.isHidden()
    assert view.clean_mode_card.isHidden()
    assert view.clean_types_card.isHidden()
    assert view.clean_qualities_card.isHidden()
    view.auto_clean_switch.btn.setChecked(True)
    assert not view.clean_mode_card.isHidden()
    assert not view.clean_types_card.isHidden()
    assert not view.clean_qualities_card.isHidden()
    ctx.run_context.get_config.assert_called_once_with(
        app_id='bagel',
        instance_idx=99,
        group_id='standalone',
    )
    view.close()


@pytest.mark.parametrize('width,height', [(1000, 600), (1280, 720)])
def test_hint_layout_has_no_clipped_text(qapp: QApplication, config: BagelConfig, width: int, height: int) -> None:
    """仅检查离屏组件几何，不启动 OneDragon 或操作桌面。"""
    ctx = MagicMock(current_instance_idx=99)
    ctx.run_context.get_config.return_value = config
    view = BagelSettingInterface(ctx)
    view.group_id = 'standalone'
    view.resize(width, height)
    view.on_interface_shown()
    view.show()
    try:
        for _ in range(5):
            qapp.processEvents()
        scroll = view.findChild(FastScrollArea)
        assert scroll.horizontalScrollBar().maximum() == 0
        for card in (view.success_rounds_card, view.failure_retries_card, view.auto_clean_switch, view.clean_mode_card):
            label = card.contentLabel
            assert label.wordWrap()
            assert label.height() >= label.heightForWidth(label.width())
            assert label.geometry().bottom() < card.height()
        for label in view.usage_card.findChildren(BodyLabel):
            assert label.height() >= label.heightForWidth(label.width())
        assert view.guide_link.url == bagel_usage.GUIDE_URL
    finally:
        view.close()
