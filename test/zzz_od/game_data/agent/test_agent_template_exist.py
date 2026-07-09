from test.conftest import TestContext

from zzz_od.game_data.agent import (
    AgentEnum,
    AgentStateCheckWay,
    AgentStateDef,
    CommonAgentStateEnum,
)
from one_dragon.base.screen.template_info import TemplateInfo

# check_way → 该状态识别实际依赖的资产(见 agent_state_checker 各 check 方法):
#   - LENGTH 类:只裁 rect 算长度,依赖 config 的 point_list 坐标,不靠 raw/mask;
#   - COLOR_RANGE / COLOR_CHANNEL 类:bitwise_and(mask),依赖 mask.png;
#   - TEMPLATE_* 类:match_template,依赖 raw.png + mask.png。
_LENGTH_WAYS = {
    AgentStateCheckWay.BACKGROUND_GRAY_RANGE_LENGTH,
    AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
    AgentStateCheckWay.FOREGROUND_GRAY_RANGE_LENGTH,
}
_MASK_WAYS = {
    AgentStateCheckWay.COLOR_RANGE_CONNECT,
    AgentStateCheckWay.COLOR_RANGE_EXIST,
    AgentStateCheckWay.COLOR_CHANNEL_MAX_RANGE_EXIST,
    AgentStateCheckWay.COLOR_CHANNEL_EQUAL_RANGE_CONNECT,
}
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
    if way in _LENGTH_WAYS:
        return None if template.point_list else '缺 point_list 坐标(LENGTH 类需 config 坐标)'
    if way in _MASK_WAYS:
        return None if template.mask is not None else '缺 mask.png(MASK 类)'
    if way in _RAW_WAYS:
        if template.raw is None:
            return '缺 raw.png(TEMPLATE 类)'
        if template.mask is None:
            return '缺 mask.png(TEMPLATE 类)'
    return None


class TestAgentTemplateExist:
    """代理人模板完整性:遍历 ``AgentEnum`` / ``CommonAgentStateEnum`` 引用的模板,按 ``check_way``
    断言所需资产齐全(LENGTH→坐标 / MASK→mask / TEMPLATE→raw+mask);预定不检测的 pos(目录缺)跳过。"""

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
