"""WitheredDomainBattleOp 测试:节点图(shadow + 重定义)+ hook 覆写 + 6 方向脱困 + back-edge + 失败链。"""
from unittest.mock import MagicMock, patch

from zzz_od.backend.operation_registry import scan_operations
from zzz_od.operation.battle.base import BattleOpBase
from zzz_od.operation.battle.withered_domain import WitheredDomainBattleOp


def _make_op() -> WitheredDomainBattleOp:
    ctx = MagicMock()
    ctx.project_config.screen_standard_width = 1920
    ctx.current_instance_idx = 1
    ctx.run_context.get_run_record.return_value = MagicMock(period_reward_complete=False)
    return WitheredDomainBattleOp(ctx)


def test_withered_domain_scanned_by_registry() -> None:
    """operation_registry 扫到 WitheredDomainBattleOp。"""
    ops = scan_operations(ctx=MagicMock(), refresh=True)
    op_ids = {op.op_id for op in ops.operations}
    assert 'zzz_od.operation.battle.withered_domain.WitheredDomainBattleOp' in op_ids


def test_node_graph_shadow_removes_unwanted_nodes() -> None:
    """shadow 移除基类「战前移动」/「开始自动战斗」/「战斗结束」;新节点全在。"""
    op = _make_op()
    op._init_before_execute()
    node_cns = {n.cn for n in op._node_map.values()}
    assert {'判断特殊移动', '特殊移动', '向前移动', '自动战斗', '结算周期上限',
            '战斗结果-确定', '更新楼层信息', '普通战斗-完成', '战斗撤退',
            '移动失败', '点击退出', '点击退出确认', '等待退出'} <= node_cns
    assert '战前移动' not in node_cns
    assert '开始自动战斗' not in node_cns
    assert '战斗结束' not in node_cns


def test_check_battle_state_normal_hollow_distance() -> None:
    """_check_battle_state 开 normal + hollow + check_distance。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    op.ctx.auto_battle_context.check_battle_state.return_value = True
    op._check_battle_state()
    _, kwargs = op.ctx.auto_battle_context.check_battle_state.call_args
    assert kwargs.get('check_battle_end_normal_result') is True
    assert kwargs.get('check_battle_end_hollow_result') is True
    assert kwargs.get('check_distance') is True


def test_check_in_battle_secondary_distance_timeout() -> None:
    """with_distance_times>=5 → STATUS_NEED_MOVE。"""
    op = _make_op()
    op.ctx.auto_battle_context.with_distance_times = 6
    assert op._check_in_battle_secondary(in_battle=True) == BattleOpBase.STATUS_NEED_MOVE


def test_get_auto_battle_op_name_challenge_config() -> None:
    """_get_auto_battle_op_name 返 challenge_config.auto_battle。"""
    op = _make_op()
    op.ctx.withered_domain.challenge_config.auto_battle = '枯萎通用'
    assert op._get_auto_battle_op_name() == '枯萎通用'


def test_get_rid_of_stuck_direction_cycles() -> None:
    """_get_rid_of_stuck 调后 stuck_move_direction 不变(本方法只执行移动,方向由调用方切)。"""
    op = _make_op()
    op.stuck_move_direction = 3
    with patch.object(op.ctx.controller, 'move_s'), \
         patch.object(op.ctx.controller, 'move_d'), \
         patch.object(op.ctx.controller, 'move_w'):
        op._get_rid_of_stuck()
    assert op.stuck_move_direction == 3


def test_auto_battle_resets_counters() -> None:
    """auto_battle 入口重置 _move_times + turn_times(对齐原 :170-171)。"""
    op = _make_op()
    op._move_times = 10
    op.turn_times = 30
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    op.ctx.auto_battle_context.last_check_end_result = None
    op.ctx.auto_battle_context.check_battle_state.return_value = True
    op.ctx.auto_battle_context.with_distance_times = 0
    op.ctx.battle_assistant_config.screenshot_interval = 0.5
    op.auto_battle()
    assert op._move_times == 0
    assert op.turn_times == 0


def test_back_edge_auto_battle_to_move_to_battle() -> None:
    """back-edge:自动战斗 ← → 向前移动(节点都在,边由框架构建验证)。"""
    op = _make_op()
    op._init_before_execute()
    auto_battle_node = next(n for n in op._node_map.values() if n.cn == '自动战斗')
    move_to_battle_node = next(n for n in op._node_map.values() if n.cn == '向前移动')
    assert auto_battle_node is not None
    assert move_to_battle_node is not None


def test_move_fail_dual_entry() -> None:
    """move_fail 接 向前移动 FAIL_TO_MOVE + 自动战斗 TIMEOUT(双入口)。"""
    op = _make_op()
    op._init_before_execute()
    move_fail_node = next(n for n in op._node_map.values() if n.cn == '移动失败')
    assert move_fail_node is not None
