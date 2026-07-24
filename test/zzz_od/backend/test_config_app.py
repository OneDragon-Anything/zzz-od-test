"""MCP add_config_item 最小闭环单测:验校验前置(拒非法)+ 合法调领域方法。

mock backend/ctx/compendium_service/config,不触真实游戏/配置。
"""
import asyncio
from unittest.mock import MagicMock

from one_dragon.base.config.config_item import ConfigItem

from zzz_od.backend.mcp.config_app import make_add_config_item


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
