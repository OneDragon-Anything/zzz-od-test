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


def test_moves_and_waits_for_next_frame(moving_op: LostVoidMoveByDet) -> None:
    """正常寻路仍持续前进，并等待下一帧。"""
    result = moving_op.move_towards()
    assert result.status == '移动中'
    moving_op.ctx.controller.start_moving_forward.assert_called_once()
    assert moving_op._moving_for_motion


def test_camera_adjustment_cannot_hide_static_scene(moving_op: LostVoidMoveByDet) -> None:
    """目标在侧面时，持续转向也不能清掉有效静止时间。"""
    target = moving_op.ctx.lost_void.detect_to_go.return_value.results[0]
    target.x1, target.x2 = 1200, 1240
    result = None
    for index in range(40):
        moving_op.last_screenshot_time = 100.0 + index * 0.25
        result = moving_op.move_towards()
        if result.status == '尝试脱困':
            break
    assert result.status == '尝试脱困'
    assert moving_op.ctx.controller.move_mouse_relative.call_count >= 2
    assert moving_op.stuck_state.stuck_times == 1


def test_arrival_stops_forward(moving_op: LostVoidMoveByDet) -> None:
    """交互到位仍先停止移动。"""
    moving_op.allow_arrival_by_interact_btn = True
    moving_op.round_by_find_area = MagicMock(return_value=OperationRoundResult(OperationRoundResultEnum.SUCCESS))
    assert moving_op.move_towards().is_success
    moving_op.ctx.controller.stop_moving_forward.assert_called_once()


def test_scene_change_stops_motion_sampling(moving_op: LostVoidMoveByDet) -> None:
    """移动期间打开选择画面不能继续按前进。"""
    moving_op.ctx.lost_void.in_normal_world.return_value = False
    moving_op.check_and_update_current_screen = MagicMock(return_value='迷失之地-通用选择')
    assert moving_op.move_towards().status == moving_op.STATUS_INTERACT
    moving_op.ctx.controller.stop_moving_forward.assert_called_once()
    assert not moving_op._moving_for_motion


def test_temporary_target_loss_clears_motion_history(moving_op: LostVoidMoveByDet) -> None:
    """目标短暂消失导致停止移动，之前的采样不能继续累计。"""
    moving_op.ctx.lost_void.detect_to_go.return_value.results = []
    moving_op._moving_for_motion = True
    moving_op.motion_detector.static_seconds = 1.5
    assert moving_op.move_towards().status == '短暂丢失目标'
    assert moving_op.motion_detector.static_seconds == 0
    assert not moving_op._moving_for_motion


@pytest.mark.parametrize('count,expected', [(0, LostVoidMoveByDet.STATUS_NO_FOUND), (9, '尝试脱困')])
def test_repeated_target_loss_enters_recovery_through_node_graph(
    moving_op: LostVoidMoveByDet, count: int, expected: str,
) -> None:
    """多次丢目标通过节点图进入脱困，不能丢弃脱困返回状态。"""
    moving_op.ctx.lost_void.detect_to_go.return_value.results = []
    moving_op.target_lost_start_time = 98.0
    moving_op.lost_target_during_move_times = count
    result = moving_op.move_towards()
    assert result.status == expected
    moving_op.ctx.controller.normal_attack.assert_not_called()


@pytest.mark.parametrize('target_class', [LostVoidDetector.CLASS_DISTANCE, LostVoidDetector.CLASS_INTERACT])
def test_entry_loss_reprioritizes_visible_target(moving_op: LostVoidMoveByDet, target_class: str) -> None:
    """入口消失但有高优先级目标时仍交还父流程重新识别。"""
    moving_op.target_type = LostVoidDetector.CLASS_ENTRY
    moving_op.ctx.lost_void.detect_to_go.return_value.results[0].detect_class.class_name = target_class
    moving_op.target_lost_start_time = 98.0
    assert moving_op.move_towards().status == moving_op.STATUS_NEED_DETECT
