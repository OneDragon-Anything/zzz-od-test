import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestEvelyn(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_evelyn_1(self):
        agent = AgentEnum.EVELYN_CHEVALIER.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for l in [0, 100]:
                    screen = self.get_test_image(f'1_{total}_{pos}_{l}')
                    if screen is None:
                        continue

                    ans = agent_state_checker.check_length_by_background_gray(self.ctx, screen, state, total, pos)
                    print(total, pos, l, ans)
                    self.assertTrue(abs(l - ans) <= 5)

    def test_evelyn_2(self):
        agent = AgentEnum.EVELYN_CHEVALIER.value
        state = agent.state_list[1]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for l in [0, 1, 2, 3]:
                    screen = self.get_test_image(f'2_{total}_{pos}_{l}')
                    if screen is None:
                        continue

                    ans = agent_state_checker.check_cnt_by_color_range(self.ctx, screen, state, total, pos)
                    print(total, pos, l, ans)
                    self.assertEqual(l, ans)
