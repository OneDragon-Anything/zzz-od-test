import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestSethLowell(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_seth_lowell(self):
        """
        赛斯
        """
        agent = AgentEnum.SETH_LOWELL.value
        for i in ['0', '75', '100']:
            screen = self.get_test_image(f'seth_lowell_{i}')
            for state in agent.state_list:
                ans = agent_state_checker.check_length_by_background_gray(self.ctx, screen, state)
                print(ans)
                self.assertTrue(ans >= int(i))