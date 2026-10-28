from zzz_od.application.hollow_zero.lost_void.operation.lost_void_stuck import (
    LostVoidStuckState,
)


def test_failed_sectors_are_not_repeated_before_alternatives() -> None:
    """八个方向都失败前，不重复选择已失败的方向。"""
    state = LostVoidStuckState()
    directions: set[str] = set()
    for _ in range(8):
        direction = state.choose_direction()
        assert direction not in directions
        directions.add(direction)
        state.penalize_direction(direction)
    assert directions == set(state.DIRECTIONS)


def test_stuck_penalizes_last_failed_direction() -> None:
    """试走后又受阻时，惩罚上次选择的方向。"""
    state = LostVoidStuckState()
    state.record_stuck()
    assert state.direction_penalties['w'] == 1
    direction = state.choose_direction()
    state.record_stuck()
    assert state.choose_direction() != direction
    assert state.direction_penalties[direction] == 1


def test_arrival_resets_episode_but_keeps_direction_memory() -> None:
    """实际到达才能结束脱困，不清空本层方向经验。"""
    state = LostVoidStuckState(stuck_times=4, attack_attempted=True, recovery_active=True)
    state.penalize_direction('a')
    state.record_arrival()
    assert state.stuck_times == 0
    assert not state.attack_attempted
    assert not state.recovery_active
    assert state.direction_penalties == {'a': 1}
    assert LostVoidStuckState().direction_penalties == {}


def test_visual_changes_do_not_end_active_recovery() -> None:
    """飞行或攻击动画不能让下一次受阻重复攻击相同障碍。"""
    state = LostVoidStuckState()
    state.record_stuck()
    state.attack_attempted = True
    for _ in range(20):
        state.record_progress()
    assert state.attack_attempted
    assert state.stuck_times == 1
    assert state.recovery_active
