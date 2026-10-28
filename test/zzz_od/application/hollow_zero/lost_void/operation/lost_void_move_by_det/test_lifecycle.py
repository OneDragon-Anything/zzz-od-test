from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    LostVoidMoveByDet,
)


def test_new_move_operation_keeps_floor_memory(moving_op: LostVoidMoveByDet) -> None:
    """父流程重新构造寻路操作后，仍避开失败方向且不重复攻击。"""
    state = moving_op.stuck_state
    state.penalize_direction('a')
    state.attack_attempted = True
    next_op = LostVoidMoveByDet(
        moving_op.ctx, LostVoidRegionType.ENTRY, moving_op.target_type, stuck_state=state,
    )
    assert next_op.stuck_state is state
    assert next_op.stuck_state.choose_direction() != 'a'
    assert next_op.stuck_state.attack_attempted


@pytest.mark.parametrize('success', [False, True])
def test_every_exit_releases_forward(moving_op: LostVoidMoveByDet, success: bool) -> None:
    """成功、失败和超时都通过结束回调释放前进键。"""
    moving_op._moving_for_motion = True
    moving_op.after_operation_done(OperationResult(success, '执行超时' if not success else '到达目标'))
    moving_op.ctx.controller.stop_moving_forward.assert_called_once()
    assert not moving_op._moving_for_motion


def test_pause_clears_sampling_but_keeps_memory(moving_op: LostVoidMoveByDet) -> None:
    """暂停不携带旧帧恢复，也不清掉本层方向经验。"""
    moving_op.stuck_state.penalize_direction('a')
    moving_op.motion_detector.static_seconds = 1.5
    moving_op._forward_start_time = 100.0
    moving_op.pause_start_time = 100.0
    moving_op.handle_pause()
    assert moving_op.motion_detector.static_seconds == 0
    assert moving_op._forward_start_time is None
    assert moving_op.stuck_state.direction_penalties == {'a': 1}
    moving_op.ctx.controller.stop_moving_forward.assert_called_once()


def test_diagonal_keys_are_released_on_failure(moving_op: LostVoidMoveByDet) -> None:
    """第二个方向按键失败时，第一个按键也必须释放。"""
    moving_op.ctx.controller.move_a = MagicMock(side_effect=[RuntimeError('输入失败'), None])
    with pytest.raises(RuntimeError, match='输入失败'):
        moving_op._move_in_direction('sa')
    moving_op.ctx.controller.move_s.assert_any_call(release=True)
    moving_op.ctx.controller.move_a.assert_any_call(release=True)


@pytest.mark.parametrize('status,finished', [
    (LostVoidMoveByDet.STATUS_ARRIVAL, True),
    (None, True),
    (LostVoidMoveByDet.STATUS_INTERACT, True),
    (LostVoidMoveByDet.STATUS_IN_BATTLE, True),
    (LostVoidMoveByDet.STATUS_NEED_DETECT, False),
    ('执行超时', False),
])
def test_recovery_ends_only_after_real_arrival(
    moving_op: LostVoidMoveByDet, status: str | None, finished: bool,
) -> None:
    """重新识别或失败不能清掉脱困记录，实际到达才清理。"""
    moving_op.stuck_state.record_stuck()
    moving_op.stuck_state.attack_attempted = True
    moving_op.after_operation_done(OperationResult(status != '执行超时', status))
    assert moving_op.stuck_state.recovery_active is not finished
    assert moving_op.stuck_state.attack_attempted is not finished
