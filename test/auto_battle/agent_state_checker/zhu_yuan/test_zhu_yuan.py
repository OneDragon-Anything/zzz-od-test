import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestZhuYuan(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_zhu_yuan(self):
        agent = AgentEnum.ZHU_YUAN.value
        for i in [0, 1, 9]:
            screen = self.get_test_image(f'zhu_yuan_{i}')
            for state in agent.state_list:
                ans = agent_state_checker.check_cnt_by_color_range(self.ctx, screen, state)
                print(ans)
                self.assertTrue(ans == i)