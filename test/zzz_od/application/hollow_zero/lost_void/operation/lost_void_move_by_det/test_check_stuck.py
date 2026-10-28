from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    LostVoidMoveByDet,
)


def test_stationary_input_is_not_stuck_without_moving(moving_op: LostVoidMoveByDet) -> None:
    """没有发出移动指令时不累计卡住。"""
    assert moving_op.check_stuck() is None
    assert moving_op.motion_detector.last_frame is None


def test_static_scene_triggers_recovery(moving_op: LostVoidMoveByDet) -> None:
    """持续移动但场景静止，进入已有脱困节点。"""
    moving_op._moving_for_motion = True
    for timestamp in [100.0, 100.5, 101.0, 101.5]:
        moving_op.last_screenshot_time = timestamp
        assert moving_op.check_stuck() is None
    moving_op.last_screenshot_time = 102.0
    result = moving_op.check_stuck()
    assert result.is_success and result.status == '尝试脱困'
    assert moving_op.stuck_state.direction_penalties['w'] == 1
    moving_op.ctx.controller.stop_moving_forward.assert_called_once()


def test_recovery_limit_fails(moving_op: LostVoidMoveByDet) -> None:
    """连续受阻超过上限，保留失败出口。"""
    moving_op.stuck_state.stuck_times = 12
    moving_op._moving_for_motion = True
    moving_op.motion_detector.static_seconds = 2.0
    result = moving_op.check_stuck()
    assert result.is_fail and result.status == '无法脱困'


def test_animation_during_recovery_keeps_attack_and_count(moving_op: LostVoidMoveByDet) -> None:
    """进入脱困后，即使帧差很大也不能把攻击记录清空。"""
    moving_op._moving_for_motion = True
    moving_op.stuck_state.record_stuck()
    moving_op.stuck_state.attack_attempted = True
    moving_op.check_stuck()
    moving_op.last_screenshot = 255 - moving_op.last_screenshot
    moving_op.last_screenshot_time += 0.5
    assert moving_op.check_stuck() is None
    assert moving_op.stuck_state.stuck_times == 1
    assert moving_op.stuck_state.attack_attempted


def test_continuous_motion_cannot_extend_forward_limit(moving_op: LostVoidMoveByDet) -> None:
    """画面一直变化也必须在前进时限内进入脱困。"""
    moving_op.move_towards()
    for index in range(1, 16):
        moving_op.last_screenshot = 255 - moving_op.last_screenshot
        moving_op.last_screenshot_time = 100.0 + index * 0.5
        assert moving_op.move_towards().status == '移动中'
        assert moving_op.motion_detector.static_seconds == 0
    moving_op.last_screenshot_time = 108.0
    moving_op.last_screenshot = 255 - moving_op.last_screenshot
    result = moving_op.move_towards()
    assert result.status == '尝试脱困'
    assert moving_op.stuck_state.recovery_active
    moving_op.ctx.controller.stop_moving_forward.assert_called_once()


def test_camera_rebaselining_does_not_reset_forward_limit(moving_op: LostVoidMoveByDet) -> None:
    """相机重新采样不能推迟独立的前进时限。"""
    moving_op.move_towards()
    moving_op.motion_detector.reset(settle_until=120.0, preserve_static=True)
    moving_op.last_screenshot_time = 108.0
    assert moving_op.move_towards().status == '尝试脱困'
