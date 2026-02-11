from test.conftest import TestContext

from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import AgentEnum


class TestBurniceWhite:

    def test_burnice_white(self, test_context: TestContext):
        agent = AgentEnum.BURNICE_WHITE.value
        state = agent.state_list[0]

        expected_map: dict[tuple[int, int, int], int] = {
            (2, 1, 0): 0,
            (2, 1, 60): 71,
            (2, 1, 100): 100,
            (2, 2, 0): 0,
            (2, 2, 60): 60,
            (2, 2, 100): 100,
            (3, 1, 0): 0,
            (3, 1, 60): 72,
            (3, 1, 100): 100,
            (3, 2, 0): 0,
            (3, 2, 60): 58,
            (3, 2, 100): 100,
            (3, 3, 0): 0,
            (3, 3, 60): 58,
            (3, 3, 100): 100,
        }

        for (total, pos, file_label), expected in expected_map.items():
            screen = test_context.get_test_image(f'{total}_{pos}_{file_label}.png', check_image_exist=False)
            if screen is None:
                continue

            ans = agent_state_checker.check_length_by_background_gray(test_context, screen, state, total, pos)
            print(total, pos, file_label, ans)
            assert abs(expected - ans) <= 5, f'{total}_{pos}_{file_label}.png: expected={expected}, got={ans}'