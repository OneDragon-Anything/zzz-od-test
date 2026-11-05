"""新加入的应用在用户动过之前保持 New 标记。"""

from unittest.mock import MagicMock

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
    ApplicationGroupConfigItem,
)


def _config() -> ApplicationGroupConfig:
    """构造不落盘的配置，只测内存里的状态流转。"""
    config = ApplicationGroupConfig.__new__(ApplicationGroupConfig)
    config._all_apps = []
    config.app_list = []
    config.save_app_list = MagicMock()
    return config


class TestNewAppFlag:

    def test_new_item_is_new(self) -> None:
        assert ApplicationGroupConfigItem(app_id='new_app', enabled=False, is_persisted=False).is_new is True

    def test_persisted_item_is_not_new(self) -> None:
        assert ApplicationGroupConfigItem(app_id='old_app', enabled=True).is_new is False

    def test_enable_clears_new_flag(self) -> None:
        """启用会写入保存顺序，New 标记随之消失。"""
        config = _config()
        item = ApplicationGroupConfigItem(app_id='new_app', enabled=False, is_persisted=False)
        config._all_apps = []
        config.app_list = [item]

        config.set_app_enable('new_app', True)

        assert item.is_new is False
        assert config._all_apps == [item]

    def test_disable_unpersisted_item_keeps_new_flag(self) -> None:
        """只是关掉未保存的新应用，不算用户接纳，仍保留 New。"""
        config = _config()
        item = ApplicationGroupConfigItem(app_id='new_app', enabled=False, is_persisted=False)
        config.app_list = [item]

        config.set_app_enable('new_app', False)

        assert item.is_new is True

    def test_set_app_order_persists_new_items(self) -> None:
        """拖拽排序会把列表里的临时应用一并纳入保存顺序。"""
        config = _config()
        item = ApplicationGroupConfigItem(app_id='new_app', enabled=False, is_persisted=False)
        config.app_list = [item]

        config.set_app_order(['new_app'])

        assert item.is_new is False
        assert config._all_apps == [item]

    def test_new_items_are_placed_at_head(self) -> None:
        """新应用排在已保存应用前面，列表里就是置顶效果。"""
        config = _config()
        saved = ApplicationGroupConfigItem(app_id='saved_app', enabled=True)
        config._all_apps = [saved]
        config.app_list = [saved]

        config.update_full_app_list(['new_app', 'saved_app'])

        assert [item.app_id for item in config.app_list] == ['new_app', 'saved_app']
        assert config.app_list[0].is_new is True
        assert config.app_list[1].is_new is False
