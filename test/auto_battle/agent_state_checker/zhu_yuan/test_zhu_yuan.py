import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestZhuYuan(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_zhu_yuan(self):
        agent = AgentEnum.ZHU_YUAN.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for cnt in [6, 9]:
                    screen = self.get_test_image(f'{total}_{pos}_{cnt}')
                    if screen is None:
                        continue
                    # if total != 3 or pos != 2 or cnt != 6:
                    #     continue

                    ans = agent_state_checker.check_cnt_by_color_range(self.ctx, screen, state, total, pos)
                    print(total, pos, cnt, ans)
                    self.assertEqual(cnt, ans)
