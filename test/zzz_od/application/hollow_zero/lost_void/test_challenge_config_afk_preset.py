"""挑战配置预设「无脑挂机刷菲林」与新增字段默认值测试。

源码在 ``lost_void_challenge_config.py``,预设在 ``config/lost_void_challenge/无脑挂机刷菲林.sample.yml``。
新增字段(smart_escape / same_faction_first / store_save_coin / route_plan_by_map / difficulty /
stop_when_no_strategy)默认关闭,原有配置的行为不变;预设把它们全部打开。
"""
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidChallengeConfig,
)


def test_new_fields_default_off() -> None:
    config = LostVoidChallengeConfig('默认-成就模式')
    assert config.smart_escape is False
    assert config.same_faction_first is False
    assert config.store_save_coin is False
    assert config.route_plan_by_map is False
    assert config.difficulty == ''
    assert config.stop_when_no_strategy is False


def test_afk_preset_turns_rules_on() -> None:
    config = LostVoidChallengeConfig('无脑挂机刷菲林')
    assert config.is_sample
    assert config.chase_new_mode is True
    assert config.smart_escape is True
    assert config.same_faction_first is True
    assert config.store_save_coin is True
    assert config.route_plan_by_map is True
    assert config.difficulty == '难度五'
    assert config.stop_when_no_strategy is True
