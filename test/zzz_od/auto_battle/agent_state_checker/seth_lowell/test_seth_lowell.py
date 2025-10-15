from test.conftest import TestContext

from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestSethLowell:

    def test_seth_lowell(self, test_context: TestContext):
        agent = AgentEnum.SETH_LOWELL.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for cnt in [0, 75, 100]:
                    screen = test_context.get_test_image(f'{total}_{pos}_{cnt}.png', check_image_exist=False)
                    if screen is None:
                        continue
                    # if total != 3 or pos != 1 or cnt != 3:
                    #     continue

                    ans = agent_state_checker.check_length_by_background_gray(test_context, screen, state, total, pos)

                    print(total, pos, cnt, ans)
                    if cnt > 0:
                        assert ans >= cnt
                    else:
                        assert cnt == ans