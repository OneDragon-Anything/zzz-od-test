"""describe_config + list_app_configs 单测。

mock backend/ctx/config,验证 schema 组装正确(set_fields/ro/list_fields/add_example/enum options)。
"""
import asyncio
from unittest.mock import MagicMock

from one_dragon.base.config.config_item import ConfigItem

from zzz_od.backend.config_router import (
    _build_set_fields,
    _build_list_fields,
    _charge_plan_item_from_dict,
    _enum_options,
    _ro_item_fields_for,
    RouterEntry,
)
from zzz_od.backend.mcp.config_app import make_describe_config, make_list_app_configs


def test_enum_options_value_not_label():
    """enum options 返回 ConfigItem.value(智能体传这个),非 label。"""
    from zzz_od.application.charge_plan.charge_plan_config import CardNumEnum
    options = _enum_options(CardNumEnum)
    # card_num: label='1张卡片' value='1'
    opt_1 = [o for o in options if o['value'] == '1'][0]
    assert opt_1['label'] == '1张卡片'
    assert opt_1['value'] == '1'


def test_list_app_configs_returns_all():
    """list_app_configs 返回全部 config + 元信息。"""
    backend = MagicMock()
    tool = make_list_app_configs(backend)
    result = asyncio.run(tool())
    assert result['ok'] is True
    app_ids = [c['app_id'] for c in result['configs']]
    assert 'charge_plan' in app_ids
    assert '_group' in app_ids
    # _group item_kind=dict
    group = [c for c in result['configs'] if c['app_id'] == '_group'][0]
    assert group['item_kind'] == 'dict'
    # standalone_app item_kind=str
    sa = [c for c in result['configs'] if c['app_id'] == 'standalone_app'][0]
    assert sa['item_kind'] == 'str'
    # charge_plan item_kind=dataclass
    cp = [c for c in result['configs'] if c['app_id'] == 'charge_plan'][0]
    assert cp['item_kind'] == 'dataclass'


def test_build_set_fields_excludes_ro():
    """set_fields 排除 _RO_FIELDS(skip_plan/run_times 等)。"""
    config = MagicMock()
    config.data = {'loop': True, 'skip_plan': False, 'run_times': 0}
    field_schema = {
        'loop': {'type': 'bool', 'desc': '循环'},
        'skip_plan': {'type': 'bool', 'desc': '跳过'},
        'run_times': {'type': 'int', 'desc': '运行次'},
    }
    ro = {'skip_plan', 'run_times', 'plan_id'}
    result = _build_set_fields(config, field_schema, ro)
    names = [f['name'] for f in result]
    assert 'loop' in names
    assert 'skip_plan' not in names
    assert 'run_times' not in names


def test_build_list_fields_add_example_filters_ro():
    """add_example 过滤 ro_item_fields(plan_id/run_times)。"""
    entry = MagicMock(spec=RouterEntry)
    entry.item_kind = 'dataclass'
    entry.id_kind = 'plan_id'
    entry.app_id = 'charge_plan'
    entry.item_schema = [
        {'name': 'category_name', 'type': 'str', 'required': True},
        {'name': 'mission_type_name', 'type': 'str', 'required': True},
        {'name': 'plan_times', 'type': 'int', 'required': False, 'default': 1},
        {'name': 'run_times', 'type': 'int', 'required': False, 'default': 0},
        {'name': 'plan_id', 'type': 'str', 'required': False, 'default': ''},
    ]
    ro_item = ['run_times', 'plan_id', 'skipped']
    result = _build_list_fields(entry, ro_item)
    assert len(result) == 1
    example = result[0]['add_example']
    assert 'plan_id' not in example
    assert 'run_times' not in example
    assert 'category_name' in example


def test_describe_config_charge_plan_schema():
    """describe_config(charge_plan) 返回 set_fields + ro + list_fields + enum options。"""
    from zzz_od.backend.config_router import get_entry
    from zzz_od.application.charge_plan.charge_plan_config import RestoreChargeEnum

    config = MagicMock()
    config.data = {'loop': True, 'restore_charge': '不使用'}
    config._RO_FIELDS = {'run_times', 'plan_id', 'last_daily_reset_dt', 'skip_plan'}

    compendium = MagicMock()
    compendium.get_charge_plan_category_list = lambda: [
        ConfigItem('实战模拟室', '实战模拟室'),
        ConfigItem('特训目标', '特训目标'),
    ]
    compendium.get_charge_plan_mission_type_list = lambda c: [ConfigItem('x', '基础材料')]

    ctx = MagicMock()
    ctx.compendium_service = compendium
    backend = MagicMock()
    backend.ctx = ctx

    # mock get_config 返回 mock config
    entry = get_entry('charge_plan')
    entry.get_config = lambda c, i, g: config

    tool = make_describe_config(backend)
    result = asyncio.run(tool('charge_plan'))

    assert result['ok'] is True
    assert result['description'] == '体力计划配置'

    # set_fields 含 loop/restore_charge,不含 skip_plan
    set_names = [f['name'] for f in result['set_fields']]
    assert 'loop' in set_names
    assert 'restore_charge' in set_names
    assert 'skip_plan' not in set_names

    # restore_charge 有 enum options({label, value})
    rc = [f for f in result['set_fields'] if f['name'] == 'restore_charge'][0]
    assert 'options' in rc
    assert len(rc['options']) == 4  # NONE/BACKUP_ONLY/ETHER_ONLY/BOTH
    assert rc['options'][0] == {'label': '不使用', 'value': '不使用'}

    # ro_fields 含 skip_plan
    assert 'skip_plan' in result['ro_fields']

    # list_fields 有 plan_list + item_fields + add_example
    assert len(result['list_fields']) == 1
    lf = result['list_fields'][0]
    assert lf['name'] == 'plan_list'
    assert lf['item_kind'] == 'dataclass'
    assert 'add_example' in lf
    assert 'plan_id' not in lf['add_example']  # 过滤 ro

    category_field = next(
        field for field in lf['item_fields']
        if field['name'] == 'category_name'
    )
    assert category_field['options'] == [
        {'label': '实战模拟室', 'value': '实战模拟室'},
        {'label': '特训目标', 'value': '特训目标'},
    ]
    assert 'options_source' not in category_field

    mission_type_field = next(
        field for field in lf['item_fields']
        if field['name'] == 'mission_type_name'
    )
    assert mission_type_field['required'] is False
    assert '特训目标/合成电池可省略' in mission_type_field['note']


def test_charge_plan_training_goal_defaults() -> None:
    """配置接口省略副本字段时，为特训目标补成校验接受的空值。"""
    item = _charge_plan_item_from_dict({'category_name': '特训目标'})

    assert item.mission_type_name == ''
    assert item.mission_name is None
