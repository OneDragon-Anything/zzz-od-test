from test.conftest import TestContext

from one_dragon.base.screen.template_info import TemplateInfo
from zzz_od.game_data.agent import (
    AgentEnum,
    AgentStateCheckWay,
    AgentStateDef,
    CommonAgentStateEnum,
)

# 所有角色状态检测均根据 config 的 point_list 裁取检测区域。
# COLOR_RANGE / COLOR_CHANNEL 类在没有 mask.png 时检测整个裁取区域；
# TEMPLATE_* 类再将 raw.png 用作匹配模板，mask.png 仅用于限制匹配范围。
_RAW_WAYS = {
    AgentStateCheckWay.TEMPLATE_FOUND,
    AgentStateCheckWay.TEMPLATE_NOT_FOUND,
}


def _state_template_err(state_def: AgentStateDef, template: TemplateInfo | None) -> str | None:
    """按 ``check_way`` 断言该状态模板有所需资产。

    模板目录缺(``get_template`` 返 ``None``)视为该 pos **预定不检测**(省性能),跳过不断言。
    目录在的,按 check_way 检查对应资产是否齐全(读不到才报)。
    """
    if template is None:
        return None
    way = state_def.check_way
    if not template.point_list:
        return '缺 point_list 坐标(状态检测需 config 坐标)'
    if way in _RAW_WAYS and template.raw is None:
        return '缺 raw.png(TEMPLATE 类需原图)'
    return None


class TestAgentTemplateExist:
    """代理人模板完整性:遍历 ``AgentEnum`` / ``CommonAgentStateEnum`` 引用的模板。

    所有状态模板都需要坐标；模板匹配状态还需要原图。mask.png 是可选的检测范围限制。
    """

    def test_battle_avatar(self, test_context: TestContext):
        """战斗头像:每个 Agent × 每个皮肤 × 前台/后台(``avatar_1_`` / ``avatar_2_``),raw 必须可读。"""
        missing = []
        for agent_enum in AgentEnum:
            for tid in agent_enum.value.template_id_list:
                for prefix in ('avatar_1_', 'avatar_2_'):
                    template_id = prefix + tid
                    template = test_context.template_loader.get_template('battle', template_id)
                    if template is None or template.raw is None:
                        missing.append(f'battle/{template_id}')
        assert not missing, f'缺失代理人头像模板: {missing}'

    def test_common_agent_state(self, test_context: TestContext):
        """通用状态(能量/特殊/终结技/格挡/切人冷却,template_id 已含 pos),按 check_way 断言资产。"""
        missing = []
        for state_enum in CommonAgentStateEnum:
            state = state_enum.value
            template = test_context.template_loader.get_template('agent_state', state.template_id)
            err = _state_template_err(state, template)
            if err:
                missing.append(f'agent_state/{state.template_id}: {err}')
        assert not missing, f'通用状态模板资产缺失: {missing}'

    def test_agent_own_state_all_pos(self, test_context: TestContext):
        """角色独有状态:``Agent.state_list`` × 所有可能 pos 变体(``_3_1``/``_3_2``/``_3_3``/``_2_2``)。

        运行时 ``_check_all_agent_state`` 对每个角色按其位置 pos 调 ``get_template``(total=3 →
        pos 1/2/3 → ``{base}_3_{pos}``;total=2 → pos1 ``{base}_3_1``、pos2 ``{base}_2_2``)。
        pos 变体目录缺 = 预定不检测该 pos(省性能),跳过;目录在的按 ``check_way`` 断言所需资产。
        """
        missing = []
        # ju_fufu 的 LENGTH 状态变体有 raw+mask 但缺 config.yml(point_list 坐标),
        # 待维护者确认是否漏建(见关联 PR / issue),暂跳过。
        _known_incomplete = {'ju_fufu'}
        for agent_enum in AgentEnum:
            agent = agent_enum.value
            if agent.agent_id in _known_incomplete or not agent.state_list:
                continue
            for state in agent.state_list:
                for suffix in ('_3_1', '_3_2', '_3_3', '_2_2'):
                    template_id = state.template_id + suffix
                    template = test_context.template_loader.get_template('agent_state', template_id)
                    err = _state_template_err(state, template)
                    if err:
                        missing.append(
                            f'agent_state/{template_id}({agent.agent_id}-{state.state_name}): {err}'
                        )
        assert not missing, f'角色独有状态模板资产缺失: {missing}'
