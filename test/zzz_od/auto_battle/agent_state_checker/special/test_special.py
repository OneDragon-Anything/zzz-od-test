from test.conftest import TestContext

from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentStateCheckWay, CommonAgentStateEnum


class TestSpecial:

    def test_special(self, test_context: TestContext):
        state_map = {
            2: [CommonAgentStateEnum.SPECIAL_21.value, CommonAgentStateEnum.SPECIAL_22.value],
            3: [CommonAgentStateEnum.SPECIAL_31.value, CommonAgentStateEnum.SPECIAL_32.value, CommonAgentStateEnum.SPECIAL_33.value]
        }

        for agent_num in [2, 3]:
            for special_pos in [0, 1, 2, 3]:
                screen = test_context.get_test_image(f'{agent_num}_{special_pos}.png', check_image_exist=False)
                if screen is None:
                    continue

                if agent_num not in state_map:
                    continue

                state_list = state_map[agent_num]

                for state_idx in range(len(state_list)):
                    agent_pos = state_idx + 1
                    state = state_list[state_idx]

                    if state.check_way == AgentStateCheckWay.COLOR_CHANNEL_MAX_RANGE_EXIST:
                        ans = agent_state_checker.check_exist_by_color_channel_max_range(test_context, screen, state)
                    elif state.check_way == AgentStateCheckWay.TEMPLATE_NOT_FOUND:
                        ans = agent_state_checker.check_template_not_found(test_context, screen, state)
                    elif state.check_way == AgentStateCheckWay.TEMPLATE_FOUND:
                        ans = agent_state_checker.check_template_found(test_context, screen, state)
                    elif state.check_way == AgentStateCheckWay.COLOR_RANGE_CONNECT:
                        ans = agent_state_checker.check_cnt_by_color_range(test_context, screen, state)
                    else:
                        raise AssertionError(f'未支持的 {state.check_way}')

                    print(agent_num, special_pos, agent_pos, ans)
                    assert (1 if special_pos == agent_pos else 0) == ans