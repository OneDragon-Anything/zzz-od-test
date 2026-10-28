from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import (
    LostVoidDetector,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    LostVoidMoveByDet,
)


def test_attack_once_then_change_direction(moving_op: LostVoidMoveByDet) -> None:
    """攻击后仍受阻时换方向，不能反复攻击而不试走。"""
    result = moving_op.get_out_of_stuck()
    assert result.status == '攻击清障'
    assert result.result == OperationRoundResultEnum.WAIT
    moving_op.ctx.controller.normal_attack.assert_called_once()
    moving_op.ctx.controller.move_a.assert_not_called()
    moving_op.get_out_of_stuck()
    moving_op.ctx.controller.normal_attack.assert_called_once()
    moving_op.ctx.controller.move_a.assert_any_call(press=True)
    moving_op.ctx.controller.move_a.assert_any_call(release=True)
    assert moving_op.stuck_state.direction_penalties['a'] == 1
    moving_op.get_out_of_stuck()
    moving_op.ctx.controller.move_d.assert_any_call(press=True)


def test_attack_clears_obstacle_before_direction_probe(moving_op: LostVoidMoveByDet) -> None:
    """攻击后出现交互到达信号时，直接交还父流程，不多走一步。"""
    assert moving_op.get_out_of_stuck().status == '攻击清障'
    moving_op.allow_arrival_by_interact_btn = True
    moving_op.round_by_find_area = MagicMock(return_value=OperationRoundResult(OperationRoundResultEnum.SUCCESS))
    assert moving_op.get_out_of_stuck().status == moving_op.STATUS_ARRIVAL
    moving_op.ctx.controller.normal_attack.assert_called_once()
    moving_op.ctx.controller.move_a.assert_not_called()


def test_unavailable_attack_uses_direction_immediately(moving_op: LostVoidMoveByDet) -> None:
    """不允许普攻时直接试走，不发送攻击。"""
    moving_op.ctx.auto_battle_context.is_normal_attack_btn_available.return_value = False
    moving_op.get_out_of_stuck()
    moving_op.ctx.controller.normal_attack.assert_not_called()
    moving_op.ctx.controller.move_a.assert_any_call(press=True)


def test_no_visible_target_skips_attack(moving_op: LostVoidMoveByDet) -> None:
    """即使普攻按钮可用，没有目标图标时也直接换方向。"""
    moving_op.ctx.lost_void.detect_to_go.return_value.results = []
    moving_op.get_out_of_stuck()
    moving_op.ctx.controller.normal_attack.assert_not_called()
    moving_op.ctx.controller.move_a.assert_any_call(press=True)


def test_escape_with_scene_progress_is_not_penalized(moving_op: LostVoidMoveByDet) -> None:
    """试走确实改变场景时，不立即记作失败。"""
    moving_op.stuck_state.attack_attempted = True
    frame = moving_op.last_screenshot
    moving_op.ctx.controller.screenshot.side_effect = [(100.0, frame), (101.0, 255 - frame)]
    moving_op.get_out_of_stuck()
    assert 'a' not in moving_op.stuck_state.direction_penalties


@pytest.mark.parametrize('in_world,battle,status', [
    (False, False, '未在大世界画面'),
    (True, True, LostVoidMoveByDet.STATUS_IN_BATTLE),
])
def test_non_navigation_screens_receive_no_escape_input(
    moving_op: LostVoidMoveByDet, in_world: bool, battle: bool, status: str,
) -> None:
    """离开大世界或遭遇战斗时不继续脱困输入。"""
    moving_op.ctx.lost_void.in_normal_world.return_value = in_world
    moving_op.ctx.lost_void.check_battle_encounter.return_value = battle
    moving_op.check_and_update_current_screen = MagicMock(return_value=None)
    result = moving_op.get_out_of_stuck()
    assert result.status == status
    moving_op.ctx.controller.normal_attack.assert_not_called()
    moving_op.ctx.controller.move_a.assert_not_called()


def test_interact_screen_is_propagated(moving_op: LostVoidMoveByDet) -> None:
    """意外打开选择画面时，返回上层处理。"""
    moving_op.ctx.lost_void.in_normal_world.return_value = False
    moving_op.check_and_update_current_screen = MagicMock(return_value='迷失之地-武备选择')
    assert moving_op.get_out_of_stuck().status == moving_op.STATUS_INTERACT


def test_arrival_is_prioritized(moving_op: LostVoidMoveByDet) -> None:
    """已经到达交互距离时交给交互流程。"""
    moving_op.allow_arrival_by_interact_btn = True
    moving_op.round_by_find_area = MagicMock(return_value=OperationRoundResult(OperationRoundResultEnum.SUCCESS))
    assert moving_op.get_out_of_stuck().status == moving_op.STATUS_ARRIVAL
    moving_op.ctx.controller.normal_attack.assert_not_called()


def test_recovery_limit_also_applies_without_target(moving_op: LostVoidMoveByDet) -> None:
    """无目标路径进入脱困也受连续次数上限约束。"""
    moving_op.stuck_state.stuck_times = 13
    assert moving_op.get_out_of_stuck().is_fail
    moving_op.ctx.controller.normal_attack.assert_not_called()


@pytest.mark.parametrize('target_type,has_distance,expected', [
    (LostVoidDetector.CLASS_INTERACT, False, LostVoidMoveByDet.STATUS_NEED_DETECT),
    (LostVoidDetector.CLASS_ENTRY, True, LostVoidMoveByDet.STATUS_NEED_DETECT),
    (LostVoidDetector.CLASS_ENTRY, False, LostVoidMoveByDet.STATUS_CONTINUE),
])
def test_escape_returns_existing_routing_status(
    moving_op: LostVoidMoveByDet, target_type: str, has_distance: bool, expected: str,
) -> None:
    """脱困后仍使用父流程已有的重新检测和继续寻路状态。"""
    moving_op.stuck_state.attack_attempted = True
    moving_op.target_type = target_type
    if has_distance:
        target = moving_op.ctx.lost_void.detect_to_go.return_value.results[0]
        target.detect_class.class_name = LostVoidDetector.CLASS_DISTANCE
    assert moving_op.get_out_of_stuck().status == expected


@pytest.mark.parametrize('in_world,battle,expected', [
    (False, False, LostVoidMoveByDet.STATUS_INTERACT),
    (True, True, LostVoidMoveByDet.STATUS_IN_BATTLE),
])
def test_screen_transition_after_escape(
    moving_op: LostVoidMoveByDet, in_world: bool, battle: bool, expected: str,
) -> None:
    """试走触发战斗或选择画面后，不再继续寻路。"""
    moving_op.stuck_state.attack_attempted = True
    moving_op.ctx.lost_void.in_normal_world.side_effect = [True, in_world]
    moving_op.ctx.lost_void.check_battle_encounter.side_effect = [False, battle]
    moving_op.check_and_update_current_screen = MagicMock(return_value='迷失之地-武备选择')
    assert moving_op.get_out_of_stuck().status == expected
