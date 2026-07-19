"""ShiyuDefenseBattleOp 测试:shadow 节点图 + hook 覆写 + _detect_move_target/_check_in_battle_secondary。"""
from unittest.mock import MagicMock, patch

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.backend.operation_registry import scan_operations
from zzz_od.operation.battle.base import BattleOpBase
from zzz_od.operation.battle.shiyu_defense import ShiyuDefenseBattleOp


def _make_op() -> ShiyuDefenseBattleOp:
    ctx = MagicMock()
    ctx.project_config.screen_standard_width = 1920
    team = MagicMock()
    team.auto_battle = '全配队通用'
    ctx.team_config.get_team_by_idx.return_value = team
    return ShiyuDefenseBattleOp(ctx, predefined_team_idx=0)


def test_shiyu_defense_scanned_by_registry() -> None:
    """operation_registry 扫到 ShiyuDefenseBattleOp;且 BattleOpBase 不被扫(Base 结尾排除)。"""
    ops = scan_operations(ctx=MagicMock(), refresh=True)
    op_ids = {op.op_id for op in ops.operations}
    assert 'zzz_od.operation.battle.shiyu_defense.ShiyuDefenseBattleOp' in op_ids
    assert 'zzz_od.operation.battle.base.BattleOpBase' not in op_ids  # Base 结尾排除


def test_node_graph_shadow_removes_unwanted_nodes() -> None:
    """shadow 移除基类「战前移动」/「开始自动战斗」(防卫战用「开始移动」替代),节点图无悬挂/无这两节点。"""
    op = _make_op()
    op._init_before_execute()  # 触发节点图构建(不抛 ValueError)
    node_cns = {n.cn for n in op._node_map.values()}
    assert '开始移动' in node_cns
    assert '战前移动' not in node_cns        # shadow 移除
    assert '开始自动战斗' not in node_cns    # shadow 移除
    assert '战斗后移动' in node_cns
    assert '战斗结束' in node_cns


def test_check_battle_state_overrides_normal_defense() -> None:
    """_check_battle_state 覆写:开 normal + defense。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    op.ctx.auto_battle_context.check_battle_state.return_value = True
    op._check_battle_state()
    _, kwargs = op.ctx.auto_battle_context.check_battle_state.call_args
    assert kwargs.get('check_battle_end_normal_result') is True
    assert kwargs.get('check_battle_end_defense_result') is True


def test_detect_move_target_distance() -> None:
    """_detect_move_target:distance_pos 非 None → MoveTarget(pos=center, source='distance')。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.distance_pos = Rect(100, 200, 300, 400)              # center=(200,300)
    op.ctx.auto_battle_context.last_check_distance = 7.2
    with patch.object(op, 'check_distance'):                # 不真跑 check_distance
        target = op._detect_move_target()
    assert target is not None and target.source == 'distance'
    assert target.pos.x == 200 and target.pos.y == 300      # Rect.center
    assert target.distance == 7.2


def test_detect_move_target_teleport_when_no_distance() -> None:
    """distance_pos None → 查传送点;命中 → MoveTarget(source='teleport')。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.distance_pos = None
    with patch.object(op, 'check_distance'), \
         patch.object(op, 'check_teleport_point', return_value=Rect(10, 20, 30, 40)):
        target = op._detect_move_target()
    assert target is not None and target.source == 'teleport'


def test_detect_move_target_none() -> None:
    """distance + 传送点都 None → 返 None。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.distance_pos = None
    with patch.object(op, 'check_distance'), \
         patch.object(op, 'check_teleport_point', return_value=None):
        assert op._detect_move_target() is None


def test_check_in_battle_secondary_countdown_timeout() -> None:
    """in_battle=True + 连续 5s 无倒计时 → STATUS_NEED_MOVE。"""
    op = _make_op()
    op.last_screenshot_time = 10.0
    op._last_countdown_check_time = 0       # 节流放行(now - 0 >= 1)
    op._no_countdown_start_time = 4.0       # 10 - 4 = 6 >= 5
    with patch.object(op, 'check_shiyu_countdown', return_value=False):
        result = op._check_in_battle_secondary(in_battle=True)
    assert result == BattleOpBase.STATUS_NEED_MOVE


def test_move_after_battle_countdown_restarts_auto_battle() -> None:
    """move_after_battle 倒计时重现 → 重启 auto_battle(start_auto_battle 被调)+ 清 _no_countdown_start_time。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    op._no_countdown_start_time = 5.0
    with patch.object(op, 'check_shiyu_countdown', return_value=True):
        op.move_after_battle()
    op.ctx.auto_battle_context.start_auto_battle.assert_called()
    assert op._no_countdown_start_time is None


def test_get_auto_battle_op_name_uses_team_config() -> None:
    """_get_auto_battle_op_name 返 team_config.auto_battle(load_auto_op 用)。"""
    op = _make_op()
    op.team_config.auto_battle = '防卫战队脚本'
    assert op._get_auto_battle_op_name() == '防卫战队脚本'
