"""LostVoidMoveByDet 卡住判定与脱困策略测试。

背景(源码 ``lost_void_move_by_det.py``):旧版卡住判定按「连续帧可见目标全部静止」累计,
单帧识别框抖动/类别抖动/目标短暂丢失都会把累计清零,实机卡墙 3 分钟也无法触发脱困,
最终 op 180 秒超时作废整层(2026-08-20 实机日志)。旧版脱困每次都换边横跳,左右抵消。

修复行为(已读源码确认):
1. 卡住判定改为「时间窗快照对比」:``check_stuck`` 每帧记录全部可见目标的
   (中心x, 中心y, 宽度) 快照(保留 10 秒);当前帧与 ≥3.5 秒前、且期间累计前进 ≥2.5 秒
   的某个快照整体保持不动(``is_same_box_constellation``:数量一致 + 一一配对
   中心距离<15 且宽度比在 0.8~1.25)即命中,2.5 秒窗口内命中 2 次判定卡住。
   中间帧抖动/丢失只影响单帧,不清零判定。
2. 脱困按本层累计次数走 6 阶段策略:同侧贴墙横滑(前进+横移)1.5/2.5 秒 →
   反侧 1.5/2.5 秒 → 大幅后撤+同侧平移 → 后撤+转向90度绕行(此阶段翻转优先侧,
   并返回 ``需要重新识别``);超过上限(12)返回 ``执行超时`` 交由上层重开。
3. 脱困后清除 ``last_target_result``(重新选目标)并重置转向校准/卡住状态。
4. ``LostVoidRunLevel.handle_find_target_fail`` 重开挑战成功后重建 ``stuck_state``,
   避免上一轮累计次数让新一轮直接放弃寻路。
"""
from unittest.mock import Mock, patch

import pytest
from test.conftest import TestContext

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.yolo.detect_utils import (
    DetectClass,
    DetectFrameResult,
    DetectObjectResult,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import (
    LostVoidDetector,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    LostVoidMoveByDet,
    LostVoidStuckState,
    MoveTargetWrapper,
    is_same_box_constellation,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)
from zzz_od.auto_battle.auto_battle_context import AutoBattleContext
from zzz_od.operation.challenge_mission.restart_in_battle import RestartInBattle


def _make_op(
    test_context: TestContext,
    target_type: str = LostVoidDetector.CLASS_ENTRY,
) -> LostVoidMoveByDet:
    return LostVoidMoveByDet(
        test_context,
        LostVoidRegionType.ENTRY,
        target_type,
        stuck_state=LostVoidStuckState(),
    )


def _make_frame(run_time: float, box_list: list[tuple[float, float, float]]) -> DetectFrameResult:
    """按 (中心x, 中心y, 宽度) 列表构造一帧识别结果(高度=宽度)。"""
    results = [
        DetectObjectResult(
            rect=[x - w / 2, y - w / 2, x + w / 2, y + w / 2],
            score=0.9,
            detect_class=DetectClass(class_id=0, class_name='0002-战斗-鸣徽'),
        )
        for x, y, w in box_list
    ]
    return DetectFrameResult(raw_image=None, results=results, run_time=run_time)


def _feed_frame(
    op: LostVoidMoveByDet,
    run_time: float,
    box_list: list[tuple[float, float, float]],
) -> OperationRoundResult | None:
    """模拟移动节点的一帧:更新截图时间后调用 check_stuck。"""
    frame = _make_frame(run_time, box_list)
    target = MoveTargetWrapper(frame.results[0])
    op.last_screenshot_time = run_time
    return op.check_stuck(frame, target)


# ---------- is_same_box_constellation 纯逻辑 ----------

def test_constellation_same_and_jitter() -> None:
    """完全相同/阈值内抖动 → 视为整体不动。"""
    old = [(100.0, 200.0, 50.0), (500.0, 210.0, 60.0)]
    assert is_same_box_constellation(old, old)
    jitter = [(108.0, 205.0, 55.0), (495.0, 202.0, 57.0)]
    assert is_same_box_constellation(old, jitter)


def test_constellation_moved_or_resized() -> None:
    """中心位移超过阈值 或 宽度变化超过区间(靠近目标) → 判为有变化。"""
    old = [(100.0, 200.0, 50.0)]
    assert not is_same_box_constellation(old, [(130.0, 200.0, 50.0)])  # 位移 30 >= 15
    assert not is_same_box_constellation(old, [(100.0, 200.0, 70.0)])  # 宽度比 1.4 > 1.25


def test_constellation_count_change_or_empty() -> None:
    """目标数量变化 或 旧快照为空 → 判为有变化。"""
    old = [(100.0, 200.0, 50.0)]
    assert not is_same_box_constellation(old, [(100.0, 200.0, 50.0), (500.0, 210.0, 60.0)])
    assert not is_same_box_constellation([], [(100.0, 200.0, 50.0)])


def test_constellation_matching_order_independent() -> None:
    """完全匹配不受遍历顺序影响(贪心会漏配的场景)。

    旧中心 0/20 新中心 8/-10(max_dis=15):贪心时 8 先占 0 导致 -10 无法配对;
    合法配对是 8->20、-10->0 应判为整体不动。
    """
    old = [(0.0, 300.0, 50.0), (20.0, 300.0, 50.0)]
    new = [(8.0, 300.0, 50.0), (-10.0, 300.0, 50.0)]
    assert is_same_box_constellation(old, new)
    # 反向传参同样成立
    assert is_same_box_constellation(new, old)


# ---------- check_stuck 时间窗判定 ----------

def test_check_stuck_static_with_jitter(test_context: TestContext, monkeypatch) -> None:
    """持续前进但画面静止(带单帧抖动) → 4 秒左右判定卡住,不被抖动清零。"""
    op = _make_op(test_context)
    stop_moving = Mock()
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', stop_moving, raising=False)

    base = [(600.0, 300.0, 50.0), (900.0, 320.0, 60.0)]
    result: OperationRoundResult | None = None
    stuck_time: float | None = None
    for i in range(32):  # 8 秒 每 0.25 秒一帧
        t = 100 + i * 0.25
        jitter = 3.0 if i % 2 == 0 else -3.0  # 模拟识别框逐帧抖动
        box_list = [(x + jitter, y, w) for x, y, w in base]
        result = _feed_frame(op, t, box_list)
        if result is not None:
            stuck_time = t
            break

    assert result is not None, '静止画面应判定为卡住'
    assert result.status == '尝试脱困'
    assert stuck_time is not None and stuck_time - 100 <= 6, '应在 6 秒内判定 而不是等 180 秒超时'
    assert op.stuck_state.stuck_times == 1
    stop_moving.assert_called()


def test_check_stuck_no_false_positive_when_approaching(test_context: TestContext, monkeypatch) -> None:
    """正常靠近目标(识别框变大、位置下移) → 不误判卡住。"""
    op = _make_op(test_context)
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', Mock(), raising=False)

    for i in range(32):  # 8 秒
        t = 200 + i * 0.25
        w = 40 * (1.02 ** i)  # 每帧 2% 的靠近速度
        box_list = [(600.0, 300.0 + i * 3, w)]
        result = _feed_frame(op, t, box_list)
        assert result is None, f'正常前进第{i}帧不应判定卡住'


def test_check_stuck_survives_target_lost(test_context: TestContext, monkeypatch) -> None:
    """目标丢失一段时间后在原位置重新出现 → 旧快照仍有效 很快判定卡住。

    旧版丢失目标会清零累计 导致周期性丢失时永远无法判定。
    """
    op = _make_op(test_context)
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', Mock(), raising=False)

    base = [(600.0, 300.0, 50.0)]
    for i in range(10):  # 前进 2.25 秒 画面静止
        assert _feed_frame(op, 300 + i * 0.25, base) is None

    # 丢失目标 2 秒(期间不调用 check_stuck) 后在原位置重新识别到
    result: OperationRoundResult | None = None
    for i in range(8):
        t = 304.5 + i * 0.25
        result = _feed_frame(op, t, base)
        if result is not None:
            break

    assert result is not None, '丢失前的快照应保留 重新识别到后应很快判定卡住'
    assert result.status == '尝试脱困'


def test_check_stuck_requires_move_seconds(test_context: TestContext, monkeypatch) -> None:
    """前进时长不足(刚开始移动)时 即使画面与旧快照一致也不判定卡住。"""
    op = _make_op(test_context)
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', Mock(), raising=False)

    base = [(600.0, 300.0, 50.0)]
    # 只有两帧间隔 4 秒:帧间隔 >=1 秒不计入前进时长 累计仍为 0
    assert _feed_frame(op, 400, base) is None
    assert _feed_frame(op, 404, base) is None, '没有累计前进时长 不应判定卡住'


def test_check_stuck_pause_not_counted_after_reset(test_context: TestContext, monkeypatch) -> None:
    """短暂丢失目标停止前进后(节点会清 last_move_frame_time) 停顿时间不计入累计前进时长。"""
    op = _make_op(test_context)
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', Mock(), raising=False)

    base = [(600.0, 300.0, 50.0)]
    assert _feed_frame(op, 500.0, base) is None
    assert _feed_frame(op, 500.25, base) is None
    assert op.total_move_seconds == pytest.approx(0.25)

    # 模拟短暂丢失目标:移动节点停止前进并清除前进帧时间
    op.last_move_frame_time = 0
    # 0.6 秒后目标重现:这段停顿不应计入
    assert _feed_frame(op, 500.85, base) is None
    assert op.total_move_seconds == pytest.approx(0.25), '停顿期不应计入累计前进时长'
    # 重现后的连续前进帧正常累计
    assert _feed_frame(op, 501.1, base) is None
    assert op.total_move_seconds == pytest.approx(0.5)


# ---------- get_out_of_stuck 脱困策略 ----------

def _mock_move_controller(test_context: TestContext, monkeypatch) -> dict[str, Mock]:
    """给 MockController 补上脱困用到的移动方法。"""
    mocks = {
        name: Mock()
        for name in [
            'start_moving_forward', 'stop_moving_forward',
            'move_w', 'move_s', 'move_a', 'move_d', 'turn_by_distance',
        ]
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(test_context.controller, name, mock, raising=False)
    return mocks


def _run_escape(op: LostVoidMoveByDet, stuck_times: int) -> OperationRoundResult:
    op.stuck_state.stuck_times = stuck_times
    with (
        patch('zzz_od.auto_battle.auto_battle_utils.switch_to_best_agent_for_moving'),
        patch.object(AutoBattleContext, 'is_normal_attack_btn_available', return_value=False),
    ):
        return op.get_out_of_stuck()


def test_escape_slide_phases_keep_side(test_context: TestContext, monkeypatch) -> None:
    """阶段0/1 同侧贴墙横滑(前进+横移) 阶段2/3 换到另一侧 不是每次换边。"""
    op = _make_op(test_context, target_type=LostVoidDetector.CLASS_INTERACT)

    for stuck_times, expect_key, expect_seconds in [
        (1, 'move_a', 1.5),
        (2, 'move_a', 2.5),
        (3, 'move_d', 1.5),
        (4, 'move_d', 2.5),
    ]:
        mocks = _mock_move_controller(test_context, monkeypatch)
        result = _run_escape(op, stuck_times)
        assert result.status == LostVoidMoveByDet.STATUS_NEED_DETECT
        mocks['start_moving_forward'].assert_called_once()
        assert mocks[expect_key].call_args.kwargs['press_time'] == expect_seconds
        other_key = 'move_d' if expect_key == 'move_a' else 'move_a'
        mocks[other_key].assert_not_called()
        assert op.stuck_state.prefer_left_escape, '前4阶段不应翻转优先侧'


def test_escape_retreat_and_detour(test_context: TestContext, monkeypatch) -> None:
    """阶段4 大幅后撤+同侧平移;阶段5 后撤转向绕行并翻转优先侧。"""
    op = _make_op(test_context, target_type=LostVoidDetector.CLASS_INTERACT)

    mocks = _mock_move_controller(test_context, monkeypatch)
    result = _run_escape(op, 5)  # 阶段4
    assert result.status == LostVoidMoveByDet.STATUS_NEED_DETECT
    assert mocks['move_s'].call_args.kwargs['press_time'] == 2.5
    assert mocks['move_a'].call_args.kwargs['press_time'] == 2
    mocks['start_moving_forward'].assert_not_called()

    mocks = _mock_move_controller(test_context, monkeypatch)
    result = _run_escape(op, 6)  # 阶段5 绕行
    assert result.status == LostVoidMoveByDet.STATUS_NEED_DETECT
    assert mocks['turn_by_distance'].call_args.args[0] == -300, '优先左侧时应向左转向绕行'
    assert mocks['move_w'].call_args.kwargs['press_time'] == 2
    assert not op.stuck_state.prefer_left_escape, '一轮策略走完应翻转优先侧'


def test_escape_clears_target_tracking(test_context: TestContext, monkeypatch) -> None:
    """脱困后清除跟踪目标与卡住状态 重新选目标 避免沿原路线撞回同一障碍。"""
    op = _make_op(test_context, target_type=LostVoidDetector.CLASS_INTERACT)
    _mock_move_controller(test_context, monkeypatch)

    frame = _make_frame(500, [(600.0, 300.0, 50.0)])
    op.last_target_result = MoveTargetWrapper(frame.results[0])
    op._record_visible_snapshot(500, frame)
    op.stuck_hit_time_list.append(500)

    _run_escape(op, 1)
    assert op.last_target_result is None
    assert len(op.visible_snapshot_list) == 0
    assert len(op.stuck_hit_time_list) == 0


def test_escape_over_limit_returns_timeout(test_context: TestContext, monkeypatch) -> None:
    """超过本层脱困上限 → 返回执行超时(上层按重开流程处理) 不再原地挣扎。"""
    op = _make_op(test_context, target_type=LostVoidDetector.CLASS_INTERACT)
    mocks = _mock_move_controller(test_context, monkeypatch)

    result = _run_escape(op, LostVoidMoveByDet.MAX_STUCK_TIMES + 1)
    assert result.is_fail
    assert result.status == Operation.STATUS_TIMEOUT
    mocks['move_a'].assert_not_called()
    mocks['move_s'].assert_not_called()


# ---------- LostVoidRunLevel 重开后重置 ----------

def test_restart_resets_stuck_state(test_context: TestContext) -> None:
    """重开挑战成功后重建 stuck_state 上一轮累计不应带入新一轮。"""
    op = LostVoidRunLevel(test_context, LostVoidRegionType.ENTRY)
    old_state = op.stuck_state
    old_state.stuck_times = LostVoidMoveByDet.MAX_STUCK_TIMES + 1

    restarted = OperationResult(success=True, status='成功')
    with patch.object(RestartInBattle, 'execute', return_value=restarted):
        result = op.handle_find_target_fail()

    assert result.is_success
    assert result.status == '准备重试'
    assert op.stuck_state is not old_state
    assert op.stuck_state.stuck_times == 0
