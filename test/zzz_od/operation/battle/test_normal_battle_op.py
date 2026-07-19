"""NormalBattleOp 测试:纯继承基类 + op_id 扫到。"""
from unittest.mock import MagicMock

from zzz_od.backend.operation_registry import scan_operations
from zzz_od.operation.battle.normal import NormalBattleOp


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.project_config.screen_standard_width = 1920
    return ctx


def test_get_auto_battle_op_name_default() -> None:
    """predefined_team_idx==-1 → auto_battle_config。"""
    op = NormalBattleOp(_make_ctx(), auto_battle_config='全配队通用', predefined_team_idx=-1)
    assert op._get_auto_battle_op_name() == '全配队通用'


def test_get_auto_battle_op_name_by_team_idx() -> None:
    """predefined_team_idx>=0 → team_list[idx].auto_battle。"""
    ctx = _make_ctx()
    team = MagicMock()
    team.auto_battle = '火队脚本'
    ctx.team_config.team_list = [team]
    op = NormalBattleOp(ctx, predefined_team_idx=0)
    assert op._get_auto_battle_op_name() == '火队脚本'


def test_normal_battle_op_scanned_by_registry() -> None:
    """operation_registry 扫到 NormalBattleOp(op_id 正确)。"""
    ops = scan_operations(ctx=MagicMock(), refresh=True)
    op_ids = {op.op_id for op in ops.operations}
    assert 'zzz_od.operation.battle.normal.NormalBattleOp' in op_ids


def test_normal_battle_op_node_graph_inherited() -> None:
    """NormalBattleOp 继承基类节点图(6 节点全在)。"""
    op = NormalBattleOp(_make_ctx())
    op._init_before_execute()
    node_cns = {n.cn for n in op._node_map.values()}
    assert {'加载自动战斗指令', '等待战斗画面加载', '战前移动', '开始自动战斗', '自动战斗', '战斗结束'} <= node_cns
