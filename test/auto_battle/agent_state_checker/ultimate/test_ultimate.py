import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum, CommonAgentStateEnum, AgentStateCheckWay


class TestUltimate(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_ultimate(self):
        state_map = {
            2: [CommonAgentStateEnum.ULTIMATE_21.value, CommonAgentStateEnum.ULTIMATE_22.value],
            3: [CommonAgentStateEnum.ULTIMATE_31.value, CommonAgentStateEnum.ULTIMATE_32.value, CommonAgentStateEnum.ULTIMATE_33.value]
        }

        for agent_num in [2, 3]:
            for ultimate_pos in [0, 1, 2, 3]:
                screen = self.get_test_image(f'{agent_num}_{ultimate_pos}')
                if screen is None:
                    continue

                if agent_num not in state_map:
                    continue

                state_list = state_map[agent_num]

                for state_idx in range(len(state_list)):
                    agent_pos = state_idx + 1
                    state = state_list[state_idx]

                    if state.check_way == AgentStateCheckWay.COLOR_RANGE_EXIST:
                        ans = agent_state_checker.check_exist_by_color_range(self.ctx, screen, state)
                    elif state.check_way == AgentStateCheckWay.TEMPLATE_NOT_FOUND:
                        ans = agent_state_checker.check_template_not_found(self.ctx, screen, state)
                    else:
                        self.fail(f'未支持的 {state.check_way}')

                    print(agent_num, ultimate_pos, agent_pos, ans)
                    self.assertEqual(ultimate_pos == agent_pos, ans)