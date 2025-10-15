from test.conftest import TestContext

from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.game_data.agent import CommonAgentStateEnum, AgentStateDef


class TestEnergy:

    def test_energy(self, test_context: TestContext):
        for total in [2, 3]:
            for pos in [1, 2, 3]:
                for cnt in [0, 60, 120]:
                    screen = test_context.get_test_image(f'{total}_{pos}_{cnt}.png', check_image_exist=False)
                    if screen is None:
                        continue
                    state = self._get_state(total, pos)
                    ans = agent_state_checker.check_length_by_foreground_gray(test_context, screen, state)

                    print(total, pos, cnt, ans)
                    if cnt > 0:
                        assert ans >= cnt
                    else:
                        assert cnt == ans

    def _get_state(self, total: int, pos: int) -> AgentStateDef:
        if total == 3:
            if pos == 1:
                return CommonAgentStateEnum.ENERGY_31.value
            elif pos == 2:
                return CommonAgentStateEnum.ENERGY_32.value
            elif pos == 3:
                return CommonAgentStateEnum.ENERGY_33.value
        elif total == 2:
            if pos == 1:
                return CommonAgentStateEnum.ENERGY_21.value
            elif pos == 2:
                return CommonAgentStateEnum.ENERGY_22.value