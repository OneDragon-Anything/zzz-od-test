import test
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum
from zzz_od.operation.hollow_zero.event import event_utils
from zzz_od.operation.hollow_zero.event.call_for_support import CallForSupport


class TestAgentStateChecker(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_seth_lowell(self):
        """
        赛斯
        """
        agent = AgentEnum.SETH_LOWELL.value
        for i in ['0', '75', '100']:
            screen = self.get_test_image(f'seth_{i}')
            for state in agent.state_list:
                ans = agent_state_checker.check_length_by_background(self.ctx, screen, state)
                print(ans)
                self.assertTrue(ans >= int(i))

    def test_jane_doe(self):
        """
        简
        """
        agent = AgentEnum.JANE_DOE.value

        # 有萨霍夫跳
        screen = self.get_test_image('jane_red')
        self.assertTrue(agent_state_checker.check_exist_by_color_range(self.ctx, screen, agent.state_list[0]))
        red_length = agent_state_checker.check_length_by_color_range(self.ctx, screen, agent.state_list[1])
        print(red_length)
        self.assertTrue(red_length >= 90)

        # 没有萨霍夫跳 没能量条
        screen = self.get_test_image('jane_blue')
        self.assertFalse(agent_state_checker.check_exist_by_color_range(self.ctx, screen, agent.state_list[0]))
        red_length = agent_state_checker.check_length_by_color_range(self.ctx, screen, agent.state_list[1])
        print(red_length)
        self.assertEqual(0, red_length)

        # 没有萨霍夫跳 有能量条
        screen = self.get_test_image('jane_100')
        self.assertFalse(agent_state_checker.check_exist_by_color_range(self.ctx, screen, agent.state_list[0]))
        red_length = agent_state_checker.check_length_by_color_range(self.ctx, screen, agent.state_list[1])
        print(red_length)
        self.assertTrue(red_length >= 99)