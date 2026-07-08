import pytest

from test.conftest import TestContext

from zzz_od.game_data.agent import AgentEnum, CommonAgentStateEnum


class TestAgentTemplateExist:
    """代理人模板完整性:遍历 ``AgentEnum`` / ``CommonAgentStateEnum`` 引用的所有模板,断言都能读到。

    覆盖三类:
    - 战斗头像(``battle`` sub_dir,每个 Agent × 皮肤 × 前台/后台);
    - 通用状态(``agent_state`` sub_dir,能量/特殊/终结技/格挡/切人冷却,template_id 已含 pos);
    - 角色独有状态(``agent_state`` sub_dir,``Agent.state_list`` × 所有可能 pos 变体)。
    """

    def test_battle_avatar(self, test_context: TestContext):
        """战斗头像:每个 Agent × 每个皮肤 × 前台/后台(``avatar_1_`` / ``avatar_2_``)。"""
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
        """通用状态(template_id 已含 pos 后缀,直接断言)。"""
        missing = []
        for state_enum in CommonAgentStateEnum:
            template_id = state_enum.value.template_id
            template = test_context.template_loader.get_template('agent_state', template_id)
            if template is None or template.raw is None:
                missing.append(f'agent_state/{template_id}')
        assert not missing, f'缺失通用状态模板: {missing}'

    @pytest.mark.xfail(reason='已知:8 个角色后台 pos 状态模板缺失,见 issue #2462', strict=True)
    def test_agent_own_state_all_pos(self, test_context: TestContext):
        """角色独有状态:``Agent.state_list`` × 所有可能 pos 变体。

        运行时 ``_check_all_agent_state`` 对每个角色按其位置调:
        total=3 → pos 1/2/3 → ``{base}_3_1`` / ``_3_2`` / ``_3_3``;
        total=2 → pos1 用 ``{base}_3_1``、pos2 用 ``{base}_2_2``(见 ``agent_state_checker.get_template``)。
        故每个角色独有状态需覆盖 ``_3_1`` / ``_3_2`` / ``_3_3`` / ``_2_2`` 全集。
        """
        pos_variants = ('_3_1', '_3_2', '_3_3', '_2_2')
        missing = []
        for agent_enum in AgentEnum:
            agent = agent_enum.value
            if not agent.state_list:
                continue
            for state in agent.state_list:
                for suffix in pos_variants:
                    template_id = state.template_id + suffix
                    template = test_context.template_loader.get_template('agent_state', template_id)
                    if template is None or template.raw is None:
                        missing.append(
                            f'agent_state/{template_id}({agent.agent_id}-{state.state_name})'
                        )
        assert not missing, f'缺失角色独有状态 pos 变体: {missing}'
