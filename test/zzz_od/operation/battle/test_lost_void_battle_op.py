"""LostVoidBattleOp 测试:节点图 + hook + 失败链 + 边 wiring + not-in_battle 分流。"""
from unittest.mock import MagicMock, patch

from zzz_od.backend.operation_registry import scan_operations
from zzz_od.operation.battle.base import BattleOpBase
from zzz_od.operation.battle.lost_void import LostVoidBattleOp


def _make_op(region_type=None) -> LostVoidBattleOp:
    ctx = MagicMock()
    ctx.project_config.screen_standard_width = 1920
    ctx.lost_void.detector = MagicMock()
    ctx.lost_void.get_auto_op_name.return_value = '全配队通用'
    rt = region_type or MagicMock()
    return LostVoidBattleOp(ctx, region_type=rt)


def test_lost_void_scanned_by_registry() -> None:
    ops = scan_operations(ctx=MagicMock(), refresh=True)
    assert 'zzz_od.operation.battle.lost_void.LostVoidBattleOp' in {op.op_id for op in ops.operations}


def test_node_graph_shadow_and_redefine() -> None:
    """shadow route_after_battle + 重定义 start_auto_battle + 失败链节点。"""
    op = _make_op()
    op._init_before_execute()
    node_cns = {n.cn for n in op._node_map.values()}
    assert {'开始自动战斗', '自动战斗', '战斗失败', '存现场', '失败退出空洞', '失败退出'} <= node_cns
    assert '战前移动' not in node_cns  # shadow
    assert '战斗结束' not in node_cns  # shadow route_after_battle


def test_handle_battle_fail_edge_from_auto_battle_with_battle_fail_status() -> None:
    """边 wiring:自动战斗 status='迷失之地-战斗失败' → 战斗失败。"""
    op = _make_op()
    op._init_before_execute()
    edges = op._node_edges_map.get('自动战斗', [])
    match = [e for e in edges if e.node_to.cn == '战斗失败']
    assert len(match) == 1
    assert match[0].status == '迷失之地-战斗失败'


def test_push_error_edge_from_auto_battle_timeout() -> None:
    """边 wiring:自动战斗 success=False status=STATUS_TIMEOUT → 存现场。"""
    from one_dragon.base.operation.operation import Operation
    op = _make_op()
    op._init_before_execute()
    edges = op._node_edges_map.get('自动战斗', [])
    match = [e for e in edges if e.node_to.cn == '存现场']
    assert len(match) == 1
    assert match[0].success is False
    assert match[0].status == Operation.STATUS_TIMEOUT


def test_fail_exit_lost_void_edge_from_push_error_failed() -> None:
    """边 wiring:存现场 success=False → 失败退出空洞。"""
    op = _make_op()
    op._init_before_execute()
    edges = op._node_edges_map.get('存现场', [])
    match = [e for e in edges if e.node_to.cn == '失败退出空洞']
    assert len(match) == 1
    assert match[0].success is False


def test_handle_fail_exit_edges_from_fail_exit_and_battle_fail() -> None:
    """边 wiring:失败退出空洞(success=True 默认)+ 战斗失败 → 失败退出。"""
    op = _make_op()
    op._init_before_execute()
    # from 失败退出空洞(success=True 默认,C1)
    edges_from_exit = op._node_edges_map.get('失败退出空洞', [])
    match_exit = [e for e in edges_from_exit if e.node_to.cn == '失败退出']
    assert len(match_exit) == 1
    assert match_exit[0].success is True
    # from 战斗失败
    edges_from_battle_fail = op._node_edges_map.get('战斗失败', [])
    match_battle = [e for e in edges_from_battle_fail if e.node_to.cn == '失败退出']
    assert len(match_battle) == 1


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
    """start_auto_battle 节点调 ctx.auto_battle_context.start_auto_battle(C3:独立节点,不每轮调)
    + M7:入口重置 _last_det_time + _last_check_finish_time = last_screenshot_time。"""
    op = _make_op()
    op.last_screenshot_time = 1.0
    op.start_auto_battle()
    op.ctx.auto_battle_context.start_auto_battle.assert_called_once()
    assert op._last_det_time == op.last_screenshot_time
    assert op._last_check_finish_time == op.last_screenshot_time
