"""ShiyuDefenseBattleOp 测试:shadow 节点图 + hook 覆写 + start_move + _check_in_battle_secondary。

结束后(move_after_battle 层间 / route 撤退·退出 / battle_timeout)交外层,不在 op。
"""
from unittest.mock import MagicMock, patch

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
    assert 'zzz_od.operation.battle.base.BattleOpBase' not in op_ids


def test_node_graph_shadow_removes_unwanted_nodes() -> None:
    """shadow 移除基类「战前移动」/「开始自动战斗」;结束后节点(战斗后移动/战斗结束/战斗超时)交外层。"""
    op = _make_op()
    op._init_before_execute()
    node_cns = {n.cn for n in op._node_map.values()}
    assert '开始移动' in node_cns
    assert '自动战斗' in node_cns
    assert '战前移动' not in node_cns        # shadow 移除
    assert '开始自动战斗' not in node_cns    # shadow 移除
    assert '战斗后移动' not in node_cns      # 结束后交外层
    assert '战斗结束' not in node_cns        # 结束后交外层
    assert '战斗超时' not in node_cns        # 结束后交外层


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


def test_check_in_battle_secondary_countdown_timeout() -> None:
    """in_battle=True + 连续 5s 无倒计时 → STATUS_NEED_MOVE。"""
    op = _make_op()
    op.last_screenshot_time = 10.0
    op._last_countdown_check_time = 0       # 节流放行(now - 0 >= 1)
    op._no_countdown_start_time = 4.0       # 10 - 4 = 6 >= 5
    with patch.object(op, 'check_shiyu_countdown', return_value=False):
        result = op._check_in_battle_secondary(in_battle=True)
    assert result == BattleOpBase.STATUS_NEED_MOVE


def test_check_in_battle_secondary_interact_btn_timeout() -> None:
    """in_battle=False + 交互键连续命中 10 次 → STATUS_NEED_MOVE。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 10.0
    op._find_interact_btn_times = 9
    with patch.object(op, 'round_by_find_area') as m:
        m.return_value.is_success = True
        result = op._check_in_battle_secondary(in_battle=False)
    assert result == BattleOpBase.STATUS_NEED_MOVE


def test_get_auto_battle_op_name_uses_team_config() -> None:
    """_get_auto_battle_op_name 返 team_config.auto_battle(load_auto_op 用)。"""
    op = _make_op()
    op.team_config.auto_battle = '防卫战队脚本'
    assert op._get_auto_battle_op_name() == '防卫战队脚本'


def test_start_move_enter_battle_on_countdown() -> None:
    """start_move:倒计时出现 → start_auto_battle + round_success('返回战斗')。"""
    op = _make_op()
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 10.0
    op._last_countdown_check_time = 0       # 节流放行
    with patch.object(op, 'check_shiyu_countdown', return_value=True):
        result = op.start_move()
    op.ctx.auto_battle_context.start_auto_battle.assert_called_once()
    assert result.is_success and result.status == '返回战斗'
