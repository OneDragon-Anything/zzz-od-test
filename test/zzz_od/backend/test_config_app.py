"""MCP add_config_item 最小闭环单测:验校验前置(拒非法)+ 合法调领域方法。

mock backend/ctx/compendium_service/config,不触真实游戏/配置。
"""
import asyncio
from unittest.mock import MagicMock

from one_dragon.base.config.config_item import ConfigItem

from zzz_od.backend.mcp.config_app import (
    make_add_config_item,
    make_delete_config_item,
    make_get_config,
    make_set_config,
)


def _make_backend(
    legal_category: str = '实战模拟室',
    legal_mission_type: str = '基础材料',
    legal_mission: str = '调查专项',
):
    """mock backend + ctx + compendium_service + config(ChargePlanConfig-like)。"""
    compendium = MagicMock()
    compendium.get_charge_plan_category_list = lambda: [ConfigItem('x', legal_category)]
    compendium.get_charge_plan_mission_type_list = lambda c: [ConfigItem('x', legal_mission_type)]
    compendium.get_charge_plan_mission_list = lambda c, m: [ConfigItem('x', legal_mission)]

    config = MagicMock()
    config.plan_list = []
    config.add_plan = MagicMock()

    run_context = MagicMock()
    run_context.get_config = MagicMock(return_value=config)

    ctx = MagicMock()
    ctx.compendium_service = compendium
    ctx.run_context = run_context
    ctx.current_instance_idx = 2

    backend = MagicMock()
    backend.ctx = ctx
    return backend, config


def test_add_config_item_legal_calls_add_plan():
    """合法 plan → ok=True + add_plan 被调(写穿领域方法)。"""
    backend, config = _make_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('charge_plan', 'plan_list', {
        'category_name': '实战模拟室',
        'mission_type_name': '基础材料',
        'mission_name': '调查专项',
        'plan_times': 1,
    }))
    assert result['ok'] is True
    assert config.add_plan.called
    item = config.add_plan.call_args[0][0]
    assert item.category_name == '实战模拟室'


def test_add_config_item_illegal_mission_type_rejected():
    """非法 mission_type → ok=False + add_plan 不调(校验前置拦)。"""
    backend, config = _make_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('charge_plan', 'plan_list', {
        'category_name': '实战模拟室',
        'mission_type_name': '不存在的类型',
        'mission_name': '调查专项',
    }))
    assert result['ok'] is False
    assert 'mission_type' in result['error']
    assert not config.add_plan.called


def test_add_config_item_unsupported_app_rejected():
    """不支持的 app_id → ok=False(路由表无)。"""
    backend, _ = _make_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('unknown_app', 'plan_list', {}))
    assert result['ok'] is False
    assert '不支持' in result['error']


# === notorious_hunt ===

def _make_notorious_hunt_backend(legal_mission_type: str = '猎血清道夫'):
    """mock backend for notorious_hunt(恶名狩猎域 mission_type 校验)。"""
    compendium = MagicMock()
    compendium.get_notorious_hunt_plan_mission_type_list = lambda c: [ConfigItem('x', legal_mission_type)]
    config = MagicMock()
    config.plan_list = []
    config.add_plan = MagicMock()
    config.delete_plan = MagicMock()
    run_context = MagicMock()
    run_context.get_config = MagicMock(return_value=config)
    ctx = MagicMock()
    ctx.compendium_service = compendium
    ctx.run_context = run_context
    ctx.current_instance_idx = 1
    backend = MagicMock()
    backend.ctx = ctx
    return backend, config


def test_add_notorious_hunt_legal():
    """合法恶名狩猎 mission_type → ok=True。"""
    backend, config = _make_notorious_hunt_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('notorious_hunt', 'plan_list', {
        'category_name': '恶名狩猎', 'mission_type_name': '猎血清道夫',
    }))
    assert result['ok'] is True
    assert config.add_plan.called


def test_add_notorious_hunt_illegal():
    """非法 mission_type → ok=False(恶名狩猎域校验)。"""
    backend, config = _make_notorious_hunt_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('notorious_hunt', 'plan_list', {
        'category_name': '恶名狩猎', 'mission_type_name': '不存在',
    }))
    assert result['ok'] is False
    assert 'mission_type' in result['error']
    assert not config.add_plan.called


def test_delete_notorious_hunt():
    """delete by plan_id → ok=True + delete_plan 被调。"""
    from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
    backend, config = _make_notorious_hunt_backend()
    plan = ChargePlanItem(category_name='恶名狩猎', mission_type_name='猎血清道夫', plan_id='nh-test-id')
    config.plan_list = [plan]
    tool = make_delete_config_item(backend)
    result = asyncio.run(tool('notorious_hunt', 'plan_list', 'nh-test-id'))
    assert result['ok'] is True
    assert config.delete_plan.called


# === standalone_app ===

def _make_standalone_app_backend(registered_apps: set[str] | None = None):
    """mock backend for standalone_app(app_id 注册校验)。"""
    if registered_apps is None:
        registered_apps = {'coffee', 'charge_plan'}
    config = MagicMock()
    config.app_list = ['coffee']
    run_context = MagicMock()
    run_context.is_app_registered = lambda app_id: app_id in registered_apps
    ctx = MagicMock()
    ctx.standalone_app_config = config
    ctx.run_context = run_context
    ctx.current_instance_idx = 1
    backend = MagicMock()
    backend.ctx = ctx
    return backend, config


def test_add_standalone_app_legal():
    """合法 app_id → ok=True(read-modify-write)。"""
    backend, config = _make_standalone_app_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('standalone_app', 'app_list', {'app_id': 'charge_plan'}))
    assert result['ok'] is True
    assert 'charge_plan' in config.app_list


def test_add_standalone_app_unregistered():
    """未注册 app_id → ok=False(is_app_registered 校验)。"""
    backend, config = _make_standalone_app_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('standalone_app', 'app_list', {'app_id': 'nonexistent'}))
    assert result['ok'] is False
    assert '未注册' in result['error']


def test_delete_standalone_app():
    """delete app_id → ok=True + app_list 移除。"""
    backend, config = _make_standalone_app_backend()
    tool = make_delete_config_item(backend)
    result = asyncio.run(tool('standalone_app', 'app_list', 'coffee'))
    assert result['ok'] is True
    assert 'coffee' not in config.app_list


# === _group(一条龙) ===

def _make_group_backend(registered_apps: set[str] | None = None):
    """mock backend for _group(ApplicationGroupConfig 经 manager)。"""
    if registered_apps is None:
        registered_apps = {'coffee', 'charge_plan'}
    item = MagicMock()
    item.app_id = 'coffee'
    config = MagicMock()
    config._all_apps = [item]
    config.remove_app = MagicMock()
    group_manager = MagicMock()
    group_manager.get_one_dragon_group_config = MagicMock(return_value=config)
    run_context = MagicMock()
    run_context.is_app_registered = lambda app_id: app_id in registered_apps
    ctx = MagicMock()
    ctx.app_group_manager = group_manager
    ctx.run_context = run_context
    ctx.current_instance_idx = 1
    backend = MagicMock()
    backend.ctx = ctx
    return backend, config


def test_add_group_rejected():
    """_group add → ok=False(app 由注册注入,不支持手动加)。"""
    backend, config = _make_group_backend()
    tool = make_add_config_item(backend)
    result = asyncio.run(tool('_group', 'app_list', {'app_id': 'coffee'}))
    assert result['ok'] is False


def test_delete_group():
    """delete app_id → ok=True + remove_app 被调。"""
    backend, config = _make_group_backend()
    tool = make_delete_config_item(backend)
    result = asyncio.run(tool('_group', 'app_list', 'coffee'))
    assert result['ok'] is True
    assert config.remove_app.called


# === get/set 测试(per config) ===

def test_get_config_charge_plan():
    """get 读字段 → ok=True + value。"""
    backend, config = _make_backend()
    config.data = {'loop': True}
    tool = make_get_config(backend)
    result = asyncio.run(tool('charge_plan', 'loop'))
    assert result['ok'] is True
    assert result['value'] is True


def test_set_config_charge_plan():
    """set 写字段 → ok=True + update+save。"""
    backend, config = _make_backend()
    config.data = {}
    config._RO_FIELDS = {'run_times', 'plan_id'}
    config.update = MagicMock()
    config.save = MagicMock()
    tool = make_set_config(backend)
    result = asyncio.run(tool('charge_plan', 'loop', False))
    assert result['ok'] is True
    config.update.assert_called_with('loop', False)
    config.save.assert_called_once()


def test_set_config_charge_plan_ro_rejected():
    """set 只读字段(run_times) → ok=False。"""
    backend, config = _make_backend()
    config._RO_FIELDS = {'run_times', 'plan_id'}
    tool = make_set_config(backend)
    result = asyncio.run(tool('charge_plan', 'run_times', 5))
    assert result['ok'] is False
    assert '只读' in result['error']


def test_get_config_notorious_hunt():
    """notorious_hunt get 读字段。"""
    backend, config = _make_notorious_hunt_backend()
    config.data = {'loop': True}
    tool = make_get_config(backend)
    result = asyncio.run(tool('notorious_hunt', 'loop'))
    assert result['ok'] is True
    assert result['value'] is True


def test_set_config_notorious_hunt():
    """notorious_hunt set 写字段。"""
    backend, config = _make_notorious_hunt_backend()
    config.data = {}
    config._RO_FIELDS = {'run_times', 'plan_id'}
    config.update = MagicMock()
    config.save = MagicMock()
    tool = make_set_config(backend)
    result = asyncio.run(tool('notorious_hunt', 'loop', False))
    assert result['ok'] is True


def test_set_config_notorious_hunt_ro_rejected():
    """notorious_hunt set 只读字段(plan_id) → ok=False。"""
    backend, config = _make_notorious_hunt_backend()
    config._RO_FIELDS = {'run_times', 'plan_id'}
    tool = make_set_config(backend)
    result = asyncio.run(tool('notorious_hunt', 'plan_id', 'xxx'))
    assert result['ok'] is False
    assert '只读' in result['error']


def test_get_config_standalone_app():
    """standalone_app get 读字段。"""
    backend, config = _make_standalone_app_backend()
    config.data = {'active_app_id': 'coffee'}
    tool = make_get_config(backend)
    result = asyncio.run(tool('standalone_app', 'active_app_id'))
    assert result['ok'] is True
    assert result['value'] == 'coffee'


def test_set_config_standalone_app():
    """standalone_app set 写字段。"""
    backend, config = _make_standalone_app_backend()
    config.data = {}
    config.update = MagicMock()
    config.save = MagicMock()
    tool = make_set_config(backend)
    result = asyncio.run(tool('standalone_app', 'active_app_id', 'charge_plan'))
    assert result['ok'] is True
    config.update.assert_called_with('active_app_id', 'charge_plan')


def test_get_config_group():
    """_group get 读字段。"""
    backend, config = _make_group_backend()
    config.data = {'app_list': [{'app_id': 'coffee', 'enabled': True}]}
    tool = make_get_config(backend)
    result = asyncio.run(tool('_group', 'app_list'))
    assert result['ok'] is True
    assert result['value'] is not None


def test_set_config_group():
    """_group set 写字段。"""
    backend, config = _make_group_backend()
    config.data = {}
    config.update = MagicMock()
    config.save = MagicMock()
    tool = make_set_config(backend)
    result = asyncio.run(tool('_group', 'loop', True))
    assert result['ok'] is True
    config.update.assert_called_with('loop', True)
