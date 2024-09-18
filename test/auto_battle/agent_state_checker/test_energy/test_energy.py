import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import CommonAgentStateEnum


class TestEnergy(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_31(self):
        screen = self.get_test_image('31_0.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_31.value)
        print(ans)
        self.assertTrue(ans <= 5)

        screen = self.get_test_image('31_lt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_31.value)
        print(ans)
        self.assertTrue(ans < 60)  # 33

        screen = self.get_test_image('31_gt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_31.value)
        print(ans)
        self.assertTrue(ans > 60)  # 62

        screen = self.get_test_image('31_120.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_31.value)
        print(ans)
        self.assertTrue(ans == 120)

    def test_32(self):
        screen = self.get_test_image('32_0.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_32.value)
        print(ans)
        self.assertTrue(ans <= 5)

        screen = self.get_test_image('32_lt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_32.value)
        print(ans)
        self.assertTrue(ans < 60)  # 57

        screen = self.get_test_image('32_gt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_32.value)
        print(ans)
        self.assertTrue(ans > 60)  # 81

        screen = self.get_test_image('32_120.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_32.value)
        print(ans)
        self.assertTrue(ans == 120)

    def test_33(self):
        screen = self.get_test_image('33_0.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_33.value)
        print(ans)
        self.assertTrue(ans <= 5)

        screen = self.get_test_image('33_lt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_33.value)
        print(ans)
        self.assertTrue(ans < 60)  # 58

        screen = self.get_test_image('33_gt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_33.value)
        print(ans)
        self.assertTrue(ans >= 60)  # 60

        screen = self.get_test_image('33_120.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_33.value)
        print(ans)
        self.assertTrue(ans == 120)

    def test_21(self):
        screen = self.get_test_image('21_0.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_21.value)
        print(ans)
        self.assertTrue(ans <= 5)

        screen = self.get_test_image('21_lt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_21.value)
        print(ans)
        self.assertTrue(ans < 60)  # 32

        screen = self.get_test_image('21_gt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_21.value)
        print(ans)
        self.assertTrue(ans > 60)  # 75

        screen = self.get_test_image('21_120.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_21.value)
        print(ans)
        self.assertTrue(ans == 120)

    def test_22(self):
        screen = self.get_test_image('22_0.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_22.value)
        print(ans)
        self.assertTrue(ans <= 5)

        screen = self.get_test_image('22_lt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_22.value)
        print(ans)
        self.assertTrue(ans < 60)  # 32

        screen = self.get_test_image('22_gt_60.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_22.value)
        print(ans)
        self.assertTrue(ans > 60)  # 75

        screen = self.get_test_image('22_120.png')
        ans = agent_state_checker.check_length_by_foreground_gray(self.ctx, screen, CommonAgentStateEnum.ENERGY_22.value)
        print(ans)
        self.assertTrue(ans == 120)
