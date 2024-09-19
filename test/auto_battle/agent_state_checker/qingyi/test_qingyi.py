import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestQingyi(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_qingyi(self):
        agent = AgentEnum.QINGYI.value
        for i in ['0', '75', '100']:
            screen = self.get_test_image(f'qingyi_{i}')
            for state in agent.state_list:
                ans = agent_state_checker.check_length_by_background_gray(self.ctx, screen, state)
                print(ans)
                self.assertTrue(ans >= int(i))

        screen = self.get_test_image('qingyi_lt_75')
        ans = agent_state_checker.check_length_by_background_gray(self.ctx, screen, agent.state_list[0])
        print(ans)
        self.assertTrue(ans < 75)  # 64

        screen = self.get_test_image('qingyi_gt_75')
        ans = agent_state_checker.check_length_by_background_gray(self.ctx, screen, agent.state_list[0])
        print(ans)
        self.assertTrue(ans > 75)  # 91
