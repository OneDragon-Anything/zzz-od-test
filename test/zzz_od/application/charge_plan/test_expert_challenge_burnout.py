"""专业挑战室燃竭模式按计划开关调整，不再强制关闭。"""

from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.operation.compendium.expert_challenge import need_toggle_burnout_mode


class TestNeedToggleBurnoutMode:

    def test_already_on_and_want_on(self) -> None:
        assert need_toggle_burnout_mode(True, True) is False

    def test_already_off_and_want_off(self) -> None:
        assert need_toggle_burnout_mode(False, False) is False

    def test_off_but_want_on(self) -> None:
        assert need_toggle_burnout_mode(False, True) is True

    def test_on_but_want_off(self) -> None:
        assert need_toggle_burnout_mode(True, False) is True


class TestChargePlanItemBurnout:

    def test_default_is_off(self) -> None:
        """默认不勾选，保持旧行为。"""
        assert ChargePlanItem().expert_challenge_burnout_on is False

    def test_round_trip_keeps_value(self) -> None:
        item = ChargePlanItem(
            category_name='专业挑战室',
            mission_type_name='代理人方案培养',
            expert_challenge_burnout_on=True,
        )

        restored = ChargePlanItem.from_dict(item.to_dict())

        assert restored.expert_challenge_burnout_on is True

    def test_old_config_without_field_defaults_off(self) -> None:
        """旧配置没有这个字段时按关闭处理。"""
        restored = ChargePlanItem.from_dict({
            'category_name': '专业挑战室',
            'mission_type_name': '代理人方案培养',
        })

        assert restored.expert_challenge_burnout_on is False


class TestAdjustBurnoutMode:
    """确认点击计入重试次数，避免状态不生效时无限循环。"""

    def _make_op(self, plan, confirm_success: bool, is_on: bool):
        from unittest.mock import MagicMock

        from zzz_od.operation.compendium.expert_challenge import ExpertChallenge

        op = object.__new__(ExpertChallenge)
        op.last_screenshot = None
        op.plan = plan
        op.round_by_find_and_click_area = MagicMock(
            return_value=MagicMock(is_success=confirm_success, status='确认')
        )
        op.round_by_find_area = MagicMock(
            return_value=MagicMock(is_success=is_on, status='开关')
        )
        op.round_by_click_area = MagicMock()
        op.round_retry = MagicMock(return_value='RETRY')
        op.round_wait = MagicMock(return_value='WAIT')
        op.round_success = MagicMock(return_value='SUCCESS')
        return op

    def test_confirm_success_counts_as_retry(self) -> None:
        from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem

        plan = ChargePlanItem(expert_challenge_burnout_on=True)
        op = self._make_op(plan, confirm_success=True, is_on=False)

        op.adjust_burnout_mode()

        op.round_retry.assert_called_once()
        op.round_wait.assert_not_called()

    def test_last_retry_does_not_click_and_checks_state(self) -> None:
        """重试快用完时不再点开关，最后机会先看画面是否已生效。"""
        from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem

        plan = ChargePlanItem(expert_challenge_burnout_on=True)
        op = self._make_op(plan, confirm_success=False, is_on=False)
        op.node_retry_times = 5
        op.node_max_retry_times = 5

        op.adjust_burnout_mode()

        op.round_by_click_area.assert_not_called()
        op.round_retry.assert_called_once()

    def test_last_retry_succeeds_when_state_matches(self) -> None:
        """最后一次机会里状态已经对上，就直接继续计划。"""
        from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem

        plan = ChargePlanItem(expert_challenge_burnout_on=True)
        op = self._make_op(plan, confirm_success=False, is_on=True)
        op.node_retry_times = 5
        op.node_max_retry_times = 5

        op.adjust_burnout_mode()

        op.round_success.assert_called_once()

    def test_matching_state_succeeds(self) -> None:
        from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem

        plan = ChargePlanItem(expert_challenge_burnout_on=True)
        op = self._make_op(plan, confirm_success=False, is_on=True)

        op.adjust_burnout_mode()

        op.round_success.assert_called_once()
        op.round_by_click_area.assert_not_called()
