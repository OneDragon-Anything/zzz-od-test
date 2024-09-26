import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestSethLowell(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_seth_lowell(self):
        agent = AgentEnum.SETH_LOWELL.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for cnt in [0, 75, 100]:
                    screen = self.get_test_image(f'{total}_{pos}_{cnt}')
                    if screen is None:
                        continue
                    # if total != 3 or pos != 1 or cnt != 3:
                    #     continue

                    ans = agent_state_checker.check_length_by_background_gray(self.ctx, screen, state, total, pos)

                    print(total, pos, cnt, ans)
                    if cnt > 0:
                        self.assertTrue(ans >= cnt)
                    else:
                        self.assertEqual(cnt, ans)