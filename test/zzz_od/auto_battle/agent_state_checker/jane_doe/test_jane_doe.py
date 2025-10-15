from test.conftest import TestContext

from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestJaneDoe:

    def test_red(self, test_context: TestContext):
        agent = AgentEnum.JANE_DOE.value
        state = agent.state_list[1]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for l in [0, 100]:
                    screen = test_context.get_test_image(f'{total}_{pos}_{l}.png', check_image_exist=False)
                    if screen is None:
                        continue

                    ans = agent_state_checker.check_length_by_foreground_color(test_context, screen, state, total, pos)
                    print(total, pos, l, ans)
                    assert abs(l - ans) <= 5

    def test_attack(self, test_context: TestContext):
        agent = AgentEnum.JANE_DOE.value
        state = agent.state_list[0]

        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for l in [0, 100]:
                    screen = test_context.get_test_image(f'{total}_{pos}_{l}.png', check_image_exist=False)
                    if screen is None:
                        continue

                    ans = agent_state_checker.check_exist_by_color_range(test_context, screen, state, total, pos)
                    print(total, pos, l, ans)
                    if l == 0:
                        assert 0 == ans
                    else:
                        assert 1 == ans
