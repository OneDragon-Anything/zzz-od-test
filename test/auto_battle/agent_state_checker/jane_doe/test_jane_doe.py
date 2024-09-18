import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestJaneDoe(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_jane_doe(self):
        """
        简
        """
        agent = AgentEnum.JANE_DOE.value

        # 有萨霍夫跳
        screen = self.get_test_image('jane_doe_red')
        self.assertTrue(agent_state_checker.check_exist_by_color_range(self.ctx, screen, agent.state_list[0]))
        red_length = agent_state_checker.check_length_by_foreground_color(self.ctx, screen, agent.state_list[1])
        print(red_length)
        self.assertTrue(red_length >= 90)

        # 没有萨霍夫跳 没能量条
        screen = self.get_test_image('jane_doe_blue')
        self.assertFalse(agent_state_checker.check_exist_by_color_range(self.ctx, screen, agent.state_list[0]))
        red_length = agent_state_checker.check_length_by_foreground_color(self.ctx, screen, agent.state_list[1])
        print(red_length)
        self.assertEqual(0, red_length)

        # 没有萨霍夫跳 有能量条
        screen = self.get_test_image('jane_doe_100')
        self.assertFalse(agent_state_checker.check_exist_by_color_range(self.ctx, screen, agent.state_list[0]))
        red_length = agent_state_checker.check_length_by_foreground_color(self.ctx, screen, agent.state_list[1])
        print(red_length)
        self.assertTrue(red_length >= 99)