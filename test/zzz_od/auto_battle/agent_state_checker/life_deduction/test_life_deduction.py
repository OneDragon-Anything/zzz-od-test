from test.conftest import TestContext

from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import CommonAgentStateEnum, AgentStateDef


class TestLifeDeduction:

    def test_life_deduction(self, test_context: TestContext):
        for total in [1, 2, 3]:
            for pos in [1]:
                for cnt in [0, 5]:
                    screen = test_context.get_test_image(f'{total}_{pos}_{cnt}.png', check_image_exist=False)
                    if screen is None:
                        continue
                    state = self._get_state(total, pos)
                    ans = agent_state_checker.check_length_by_foreground_color(test_context, screen, state)

                    print(total, pos, cnt, ans)
                    if cnt > 0:
                        assert ans >= cnt
                    else:
                        assert cnt == ans

    def _get_state(self, total: int, pos: int) -> AgentStateDef:
        if total == 3:
            return CommonAgentStateEnum.LIFE_DEDUCTION_31.value
        elif total in [1, 2]:
            return CommonAgentStateEnum.LIFE_DEDUCTION_21.value
