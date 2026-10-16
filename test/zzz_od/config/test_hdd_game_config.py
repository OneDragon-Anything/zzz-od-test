"""机械硬盘配置的默认值、保存和异常 YAML 值验证。"""

from unittest.mock import MagicMock

import pytest

from zzz_od.config.game_config import GameConfig


def make_config(data: dict | None = None) -> GameConfig:
    """构造不读写用户配置的实例。"""
    config = GameConfig.__new__(GameConfig)
    config.data = {} if data is None else data.copy()
    config.save = MagicMock()
    return config


def test_default_is_opt_in() -> None:
    """旧配置缺少新字段时，默认模式不变。"""
    config = make_config()
    assert config.hdd_mode is False
    assert config.hdd_battle_loading_timeout == 180
    assert config.data == {}


def test_settings_save_per_instance() -> None:
    """修改一份配置不会改变另一份配置。"""
    hdd_config = make_config()
    default_config = make_config()
    hdd_config.hdd_mode = True
    hdd_config.hdd_battle_loading_timeout = 240
    assert hdd_config.data == {'hdd_mode': True, 'hdd_battle_loading_timeout': 240}
    assert hdd_config.save.call_count == 2
    assert default_config.hdd_mode is False
    assert default_config.hdd_battle_loading_timeout == 180


@pytest.mark.parametrize(
    'value, expected', [(0, 60), (60, 60), (240, 240), (600, 600), (999, 600)]
)
def test_timeout_is_bounded(value: int, expected: int) -> None:
    """手改 YAML 超出范围时仍有有限等待上限。"""
    assert (
        make_config({'hdd_battle_loading_timeout': value}).hdd_battle_loading_timeout
        == expected
    )


@pytest.mark.parametrize('value', [None, True, '180', 1.5])
def test_invalid_timeout_uses_default(value: object) -> None:
    """非整数配置不会造成无限等待或运行崩溃。"""
    assert (
        make_config({'hdd_battle_loading_timeout': value}).hdd_battle_loading_timeout
        == 180
    )


@pytest.mark.parametrize('value', [False, None, 'false', 'true', 1])
def test_only_yaml_boolean_enables_mode(value: object) -> None:
    """错误的字符串或数字配置不会意外启用模式。"""
    assert make_config({'hdd_mode': value}).hdd_mode is False
