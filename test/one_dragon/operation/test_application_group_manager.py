from unittest.mock import MagicMock, patch

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
    ApplicationGroupConfigItem,
)
from one_dragon.base.operation.application.application_group_manager import (
    ApplicationGroupManager,
)


def test_one_dragon_runtime_list_only_uses_default_apps() -> None:
    """一条龙运行时只加载默认应用，同时保留 YAML 中其他原始项。"""
    manager = ApplicationGroupManager(MagicMock())
    manager.set_default_apps(['default_app'])

    original_items = [
        ApplicationGroupConfigItem(app_id='standalone_app', enabled=True),
        ApplicationGroupConfigItem(app_id='internal_app', enabled=True),
        ApplicationGroupConfigItem(app_id='unregistered_app', enabled=True),
    ]
    config = MagicMock()
    config.is_file_exists = True
    config._all_apps = original_items.copy()

    with patch(
        'one_dragon.base.operation.application.application_group_manager.ApplicationGroupConfig',
        return_value=config,
    ):
        result = manager._init_one_dragon_group_config(instance_idx=1)

    assert result is config
    assert config._all_apps == original_items
    config.save_app_list.assert_not_called()
    config.update_full_app_list.assert_called_once_with(['default_app'])


def test_update_full_app_list_preserves_non_default_saved_items() -> None:
    """运行时过滤不应删除 YAML 中保存的其他应用 ID。"""
    config = ApplicationGroupConfig.__new__(ApplicationGroupConfig)
    standalone = ApplicationGroupConfigItem(app_id='standalone_app', enabled=True)
    internal = ApplicationGroupConfigItem(app_id='internal_app', enabled=True)
    missing = ApplicationGroupConfigItem(app_id='missing_app', enabled=True)
    original_items = [standalone, internal, missing]
    config._all_apps = original_items.copy()
    config.app_list = original_items.copy()

    config.update_full_app_list(['default_app'])

    assert config._all_apps == original_items
    assert [item.app_id for item in config.app_list] == ['default_app']
    assert config.app_list[0].is_persisted is False


def test_remove_app_deletes_it_from_all_lists_and_saves() -> None:
    """永久移除应同时更新完整列表、显示列表并写回配置。"""
    config = ApplicationGroupConfig.__new__(ApplicationGroupConfig)
    removed_item = ApplicationGroupConfigItem(app_id='removed_app', enabled=True)
    kept_item = ApplicationGroupConfigItem(app_id='kept_app', enabled=True)
    config._all_apps = [removed_item, kept_item]
    config.app_list = [removed_item, kept_item]
    config.save_app_list = MagicMock()

    config.remove_app('removed_app')

    assert config._all_apps == [kept_item]
    assert config.app_list == [kept_item]
    config.save_app_list.assert_called_once_with()


def test_set_one_dragon_app_enable_only_updates_status() -> None:
    """切换一条龙应用状态时不删除 YAML 中的应用 ID。"""
    manager = ApplicationGroupManager(MagicMock())
    config = MagicMock()

    result = manager.set_one_dragon_app_enable(config, 'default_app', False)

    assert result is None
    config.set_app_enable.assert_called_once_with('default_app', False)
    config.remove_app.assert_not_called()
