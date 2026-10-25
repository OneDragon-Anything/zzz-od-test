"""活跃度领奖结果的分支测试；不初始化控制器或连接真实游戏。"""
from types import SimpleNamespace
from unittest.mock import Mock

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from zzz_od.application.engagement_reward.engagement_reward_app import EngagementRewardApp


def outcome(success: bool, status: str | None = None) -> OperationRoundResult:
    """构造无副作用的节点结果。"""
    return OperationRoundResult(
        OperationRoundResultEnum.SUCCESS if success else OperationRoundResultEnum.FAIL,
        status,
    )


def fake_operation() -> SimpleNamespace:
    """仅替换识别和点击辅助函数，不调用 Application 构造函数。"""
    return SimpleNamespace(
        last_screenshot=object(),
        round_by_find_area=Mock(),
        round_by_find_and_click_area=Mock(),
        round_success=lambda status: outcome(True, status),
        round_fail=lambda status: outcome(False, status),
    )


def test_already_claimed_highest_mark_is_verified() -> None:
    """最高档已有勾号，无需本轮出现领取弹窗。"""
    op = fake_operation()
    op.round_by_find_area.return_value = outcome(True)
    result = EngagementRewardApp.check_engagement(op)
    assert result.is_success
    assert result.status == '日常最高档奖励已领取'


def test_missing_mark_is_not_reported_as_unclaimed() -> None:
    """识别失败只能表示待核实，不断言资源没有到账。"""
    op = fake_operation()
    op.round_by_find_area.return_value = outcome(False)
    result = EngagementRewardApp.check_engagement(op)
    assert not result.is_success
    assert result.status == '未识别到最高档奖励已领取'


def test_preview_closed_does_not_claim_success() -> None:
    """预览已关闭仍需最高档勾号核验。"""
    op = fake_operation()
    op.round_by_find_and_click_area.side_effect = [outcome(False), outcome(True)]
    op.round_by_find_area.return_value = outcome(True)
    result = EngagementRewardApp.check_reward(op)
    assert result.is_success
    assert result.status == '奖励预览已关闭，领取状态待核实'


def test_real_claim_dialog_keeps_existing_status() -> None:
    """新领取弹窗继续保留原日志契约。"""
    op = fake_operation()
    op.round_by_find_and_click_area.return_value = outcome(True)
    assert EngagementRewardApp.check_reward(op).status == '日常奖励领取成功'


def test_preview_close_failure_cannot_verify_receipt() -> None:
    """关闭失败不能跳过核验。"""
    op = fake_operation()
    op.round_by_find_and_click_area.side_effect = [outcome(False), outcome(False)]
    op.round_by_find_area.return_value = outcome(True)
    assert not EngagementRewardApp.check_reward(op).is_success
