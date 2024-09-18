import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import CommonAgentStateEnum


class TestLifeDeduction(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_life_deduction(self):
        screen = self.get_test_image('life_0.png')
        ans = agent_state_checker.check_length_by_foreground_color(self.ctx, screen, CommonAgentStateEnum.LIFE_DEDUCTION.value)
        print(ans)
        self.assertTrue(ans == 0)

        screen = self.get_test_image('life_gt_0.png')
        ans = agent_state_checker.check_length_by_foreground_color(self.ctx, screen, CommonAgentStateEnum.LIFE_DEDUCTION.value)
        print(ans)
        self.assertTrue(ans > 0)