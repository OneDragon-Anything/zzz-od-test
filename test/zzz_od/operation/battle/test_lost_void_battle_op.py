"""LostVoidBattleOp 测试:节点图 + wait_battle + hook + not-in_battle 分流。

移动(进下一区域)/ 失败链 / 结束后操作交外层,不在 op。
"""
from unittest.mock import MagicMock, patch

from zzz_od.backend.operation_registry import scan_operations
from zzz_od.operation.battle.base import BattleOpBase
from zzz_od.operation.battle.lost_void import LostVoidBattleOp


def _make_op(region_type=None, wait_battle: bool = False) -> LostVoidBattleOp:
    ctx = MagicMock()
    ctx.project_config.screen_standard_width = 1920
    ctx.lost_void.detector = MagicMock()
    ctx.lost_void.get_auto_op_name.return_value = '全配队通用'
    rt = region_type or MagicMock()
    return LostVoidBattleOp(ctx, region_type=rt, wait_battle=wait_battle)


def test_lost_void_scanned_by_registry() -> None:
    ops = scan_operations(ctx=MagicMock(), refresh=True)
    assert 'zzz_od.operation.battle.lost_void.LostVoidBattleOp' in {op.op_id for op in ops.operations}


def test_node_graph_shadow_and_redefine() -> None:
    """shadow pre_battle_move + 覆写 wait_battle_screen + 重定义 start_auto_battle;失败链交外层。"""
    op = _make_op()
    op._init_before_execute()
    node_cns = {n.cn for n in op._node_map.values()}
    assert {'等待战斗画面加载', '开始自动战斗', '自动战斗'} <= node_cns
    assert '战前移动' not in node_cns        # shadow
    assert '战斗结束' not in node_cns        # 基类移除 route_after_battle
    # 失败链交外层
    assert '战斗失败' not in node_cns
    assert '存现场' not in node_cns
    assert '失败退出空洞' not in node_cns
    assert '失败退出' not in node_cns


def test_wait_battle_false_skips_wait() -> None:
    """wait_battle=False → wait_battle_screen 直接 round_success(跳过,外层已判)。"""
    op = _make_op(wait_battle=False)
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    result = op.wait_battle_screen()
    assert result.is_success
    op.ctx.lost_void.check_battle_encounter.assert_not_called()


def test_wait_battle_true_polls_check_battle_encounter() -> None:
    """wait_battle=True → check_battle_encounter 命中 → round_success。"""
    op = _make_op(wait_battle=True)
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    op.ctx.lost_void.check_battle_encounter.return_value = True
    result = op.wait_battle_screen()
    assert result.is_success
    op.ctx.lost_void.check_battle_encounter.assert_called_once()


def test_check_battle_state_no_flag() -> None:
    """_check_battle_state 不传 flag。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    op.ctx.auto_battle_context.check_battle_state.return_value = True
    op._check_battle_state()
    _, kwargs = op.ctx.auto_battle_context.check_battle_state.call_args
    assert not kwargs.get('check_battle_end_normal_result')


def test_check_in_battle_secondary_distance_timeout() -> None:
    """in_battle + detector 识别到交互 + _no_in_battle_times >= 10 → STATUS_NEED_MOVE。"""
    op = _make_op()
    op.last_screenshot_time = 1.0  # 绕过节流(now - _last_det_time=0 >= 0.8)
    op._no_in_battle_times = 11
    op._last_frame_in_battle = True
    op._current_frame_in_battle = True
    op.ctx.model_config.lost_void_det_gpu = False  # 走同步路径,避免 gpu_executor
    op.detector.is_frame_with_all.return_value = (True, False, False)  # 识别到交互 → no_in_battle=True
    assert op._check_in_battle_secondary(in_battle=True) == BattleOpBase.STATUS_NEED_MOVE


def test_check_in_battle_secondary_not_in_battle_battle_fail() -> None:
    """not-in_battle 分流:_no_in_battle_times>=3 + screen='迷失之地-战斗失败' → 返该 status。"""
    op = _make_op()
    op.last_screenshot_time = 1.0  # 节流放行(1.0 - 0 >= 1)
    op._no_in_battle_times = 3
    op.ctx.model_config.ocr_use_gpu = False  # 走同步路径,避免 gpu_executor
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=False)), \
         patch.object(op, 'check_and_update_current_screen', return_value='迷失之地-战斗失败'), \
         patch.object(op, 'round_by_find_and_click_area', return_value=MagicMock(is_success=False)):
        result = op._check_in_battle_secondary(in_battle=False)
    assert result == '迷失之地-战斗失败'


def test_check_in_battle_secondary_not_in_battle_need_move() -> None:
    """not-in_battle 分流:_no_in_battle_times>=3 + screen='迷失之地-武备选择' → STATUS_NEED_MOVE。"""
    op = _make_op()
    op.last_screenshot_time = 1.0
    op._no_in_battle_times = 3
    op.ctx.model_config.ocr_use_gpu = False
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=False)), \
         patch.object(op, 'check_and_update_current_screen', return_value='迷失之地-武备选择'), \
         patch.object(op, 'round_by_find_and_click_area', return_value=MagicMock(is_success=False)):
        result = op._check_in_battle_secondary(in_battle=False)
    assert result == BattleOpBase.STATUS_NEED_MOVE


def test_get_auto_battle_op_name() -> None:
    op = _make_op()
    op.ctx.lost_void.get_auto_op_name.return_value = '迷失通用'
    assert op._get_auto_battle_op_name() == '迷失通用'


def test_start_auto_battle_resets_timestamps() -> None:
    """start_auto_battle 节点调 ctx.auto_battle_context.start_auto_battle + 入口重置时间戳。"""
    op = _make_op()
    op.last_screenshot_time = 1.0
    op.start_auto_battle()
    op.ctx.auto_battle_context.start_auto_battle.assert_called_once()
    assert op._last_det_time == op.last_screenshot_time
    assert op._last_check_finish_time == op.last_screenshot_time
