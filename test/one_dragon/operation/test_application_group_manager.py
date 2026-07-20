from unittest.mock import MagicMock, patch

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
    ApplicationGroupConfigItem,
)
from one_dragon.base.operation.application.application_group_manager import (
    ApplicationGroupManager,
)


def test_configured_non_default_app_remains_in_one_dragon_list() -> None:
    """已开启的非默认应用继续显示，已禁用或未配置的应用不显示。"""
    ctx = MagicMock()
    registered_app_ids = {
        'default_app',
        'configured_app',
        'disabled_app',
        'unconfigured_app',
    }
    ctx.run_context.is_app_registered.side_effect = registered_app_ids.__contains__

    manager = ApplicationGroupManager(ctx)
    manager.set_default_apps(['default_app'])

    config = MagicMock()
    config.is_file_exists = True
    config._all_apps = [
        ApplicationGroupConfigItem(app_id='configured_app', enabled=True),
        ApplicationGroupConfigItem(app_id='disabled_app', enabled=False),
        ApplicationGroupConfigItem(app_id='unregistered_app', enabled=True),
    ]

    with patch(
        'one_dragon.base.operation.application.application_group_manager.ApplicationGroupConfig',
        return_value=config,
    ):
        result = manager._init_one_dragon_group_config(instance_idx=1)

    assert result is config
    assert [item.app_id for item in config._all_apps] == [
        'configured_app',
        'unregistered_app',
    ]
    config.save_app_list.assert_called_once_with()
    config.update_full_app_list.assert_called_once_with(['default_app', 'configured_app'])


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


def test_disabling_migrated_app_removes_it_from_config() -> None:
    """非默认组迁移应用被禁用后应永久移除，默认组应用只切换状态。"""
    manager = ApplicationGroupManager(MagicMock())
    manager.set_default_apps(['default_app'])
    config = MagicMock()

    removed = manager.set_one_dragon_app_enable(config, 'migrated_app', False)

    assert removed is True
    config.remove_app.assert_called_once_with('migrated_app')
    config.set_app_enable.assert_not_called()

    removed = manager.set_one_dragon_app_enable(config, 'default_app', False)

    assert removed is False
    config.set_app_enable.assert_called_once_with('default_app', False)
