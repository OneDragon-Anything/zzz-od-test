import test
from zzz_od.game_data.agent import AgentEnum
from zzz_od.hollow_zero.hollow_battle import HollowBattle
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.call_for_support import CallForSupport


class TestHollowBattle(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_period_reward_complete(self):
        screen = self.get_test_image('with_reward.png')
        op = HollowBattle(self.ctx)
        result = op.round_by_find_area(screen, '零号空洞-战斗', '通关-丁尼奖励')
        self.assertTrue(result.is_success)