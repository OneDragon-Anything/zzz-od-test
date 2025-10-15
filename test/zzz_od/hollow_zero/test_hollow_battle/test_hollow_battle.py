from test.conftest import TestContext

from zzz_od.hollow_zero.hollow_battle import HollowBattle


class TestHollowBattle:

    def test_period_reward_complete(self, test_context: TestContext):
        screen = test_context.get_test_image('with_reward.png')
        op = HollowBattle(test_context)
        result = op.round_by_find_area(screen, '零号空洞-战斗', '通关-丁尼奖励')
        assert result.is_success is True