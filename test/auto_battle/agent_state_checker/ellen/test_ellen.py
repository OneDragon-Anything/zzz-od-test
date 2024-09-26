import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestEllen(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_ellen(self):
        agent = AgentEnum.ELLEN.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for cnt in [0, 1, 2, 3, 4, 5, 6]:
                    screen = self.get_test_image(f'{total}_{pos}_{cnt}')
                    if screen is None:
                        continue
                    ans = agent_state_checker.check_cnt_by_color_range(self.ctx, screen, state, total, pos)
                    print(total, pos, cnt, ans)
                    self.assertEqual(cnt, ans)