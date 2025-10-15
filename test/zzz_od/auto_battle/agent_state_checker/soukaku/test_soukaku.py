from test.conftest import TestContext

from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestSoukaku:

    def test_soukaku(self, test_context: TestContext):
        agent = AgentEnum.SOUKAKU.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for cnt in [0, 1, 2, 3, 4, 5, 6]:
                    screen = test_context.get_test_image(f'{total}_{pos}_{cnt}.png', check_image_exist=False)
                    if screen is None:
                        continue
                    # if total != 3 or pos != 1 or cnt != 3:
                    #     continue
                    ans = agent_state_checker.check_cnt_by_color_range(test_context, screen, state, total, pos)
                    print(total, pos, cnt, ans)
                    assert cnt == ans