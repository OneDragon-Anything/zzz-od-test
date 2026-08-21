from types import SimpleNamespace

import pytest

from one_dragon.base.config.yaml_config import YamlConfig
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.backend.config_router import _build_routes


class _CompendiumService:

    def get_charge_plan_category_list(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(value='实战模拟室')]

    def get_charge_plan_mission_type_list(self, category_name: str) -> list[SimpleNamespace]:
        return [SimpleNamespace(value='基础材料')]

    def get_charge_plan_mission_list(
        self,
        category_name: str,
        mission_type_name: str,
    ) -> list[SimpleNamespace]:
        return [SimpleNamespace(value='调查专项')]


def _new_config() -> ChargePlanConfig:
    config = object.__new__(ChargePlanConfig)
    config.data = {}
    config.plan_list = []
    return config


def _skip_yaml_save(config: YamlConfig) -> None:
    return None


def test_old_item_defaults_to_disabled() -> None:
    item = ChargePlanItem.from_dict({'category_name': '实战模拟室'})

    assert item.battle_timeout_seconds == 0


def test_timeout_is_serialized() -> None:
    item = ChargePlanItem(battle_timeout_seconds=120)

    assert item.to_dict()['battle_timeout_seconds'] == 120


def test_timeout_boundaries_are_valid() -> None:
    ctx = SimpleNamespace(compendium_service=_CompendiumService())

    assert ChargePlanConfig.validate_item(ctx, ChargePlanItem(battle_timeout_seconds=0)) is None
    assert ChargePlanConfig.validate_item(ctx, ChargePlanItem(battle_timeout_seconds=600)) is None


@pytest.mark.parametrize(
    ('category_name', 'expected_seconds'),
    [
        ('实战模拟室', 120),
        ('区域巡防', 120),
        ('专业挑战室', 180),
        ('恶名狩猎', 300),
    ],
)
def test_s_rank_timeout_presets(category_name: str, expected_seconds: int) -> None:
    assert charge_plan_const.S_RANK_BATTLE_TIMEOUT_SECONDS[category_name] == expected_seconds


def test_unknown_category_has_no_s_rank_timeout_preset() -> None:
    assert charge_plan_const.S_RANK_BATTLE_TIMEOUT_SECONDS.get('合成电池') is None
    assert charge_plan_const.S_RANK_BATTLE_TIMEOUT_SECONDS.get('未知副本') is None


def test_timeout_outside_range_is_invalid() -> None:
    ctx = SimpleNamespace()

    for value in (-1, 601):
        error = ChargePlanConfig.validate_item(ctx, ChargePlanItem(battle_timeout_seconds=value))
        assert error is not None
        assert '0..600' in error


def test_normal_and_double_reward_configs_save_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(YamlConfig, 'save', _skip_yaml_save)
    config = _new_config()
    config.plan_list = [ChargePlanItem(battle_timeout_seconds=90)]

    config.save()
    assert config.data['plan_list'][0]['battle_timeout_seconds'] == 90

    config.combat_simulation_double_reward_config = ChargePlanItem(battle_timeout_seconds=180)
    saved_double = config.data['combat_simulation_double_reward_config']
    assert saved_double['battle_timeout_seconds'] == 180


def test_backend_schema_describes_timeout() -> None:
    route = _build_routes()['charge_plan']
    timeout_field = next(
        field for field in route.item_schema
        if field['name'] == 'battle_timeout_seconds'
    )

    assert timeout_field['type'] == 'int'
    assert timeout_field['default'] == 0
    assert '0..600' in timeout_field['note']
    assert '实战模拟室/区域巡防 120' in timeout_field['note']
    assert '专业挑战室 180' in timeout_field['note']
    assert '恶名狩猎 300' in timeout_field['note']
