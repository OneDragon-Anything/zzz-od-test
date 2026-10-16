import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from zzz_od.application.bagel import bagel_usage
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.gui.app_setting.bagel_setting_interface import BagelSettingInterface

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@pytest.fixture(scope='module')
def qapp() -> QApplication:
    """创建不操作桌面的 Qt 实例。"""
    return QApplication.instance() or QApplication([])


def test_settings_rebind_updates_selection_description(
    qapp: QApplication,
    config: BagelConfig,
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
    other.sell_interval = 3
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
        assert view.sell_interval_card.spin_box.value() == 3
        assert view.sell_interval_card.isHidden()
        assert set(view.clean_types_card.get_value()) == {'装备', '贵重物品'}
        assert view.clean_types_card.contentLabel.text() == '已选 2 项'
        assert view.clean_qualities_card.contentLabel.text() == '已选 2 项'
        assert Path(other.file_path).read_bytes() == before
    finally:
        view.close()


def test_settings_save_and_show_relevant_options(
    qapp: QApplication, config: BagelConfig
) -> None:
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
    assert view.sell_interval_card.spin_box.value() == 1
    view.sell_interval_card.spin_box.setValue(2)
    assert BagelConfig(99, 'standalone').sell_interval == 2
    assert view.sell_interval_card.contentLabel.text() == bagel_usage.SELL_INTERVAL_HINT
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
