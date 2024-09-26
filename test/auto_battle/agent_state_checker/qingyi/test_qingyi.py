import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestQingyi(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_qingyi(self):
        agent = AgentEnum.QINGYI.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for l in [0, 100]:
                    screen = self.get_test_image(f'{total}_{pos}_{l}')
                    if screen is None:
                        continue

                    ans = agent_state_checker.check_length_by_background_gray(self.ctx, screen, state, total, pos)
                    print(total, pos, l, ans)
                    self.assertTrue(abs(l - ans) <= 5)
