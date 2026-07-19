"""BattleOpBase 基类单元测试。

聚焦可单测部分(MoveTarget/STATUS/抽象/_move_one_step/节点图构建/hook 默认签名)。
完整 auto_battle 跑(含 auto_battle_context 真跑 + 战斗 fixture)留 GREEN 实跑验证(见 spec §13)。
"""
from dataclasses import is_dataclass
from unittest.mock import MagicMock

import pytest

from zzz_od.operation.battle.base import BattleOpBase, MoveTarget


class _ConcreteBattleOp(BattleOpBase):
    """测试用具体子类(覆写抽象 hook)。"""
    def _get_auto_battle_op_name(self) -> str | None:
        return '全配队通用'


def _make_ctx() -> MagicMock:
    """构造带 screen_standard_width 的 mock ctx(__init__ 要 // 2)。"""
    ctx = MagicMock()
    ctx.project_config.screen_standard_width = 1920
    return ctx


def test_move_target_is_dataclass() -> None:
    """MoveTarget 是 dataclass,字段 pos/distance/source。"""
    assert is_dataclass(MoveTarget)
    t = MoveTarget(pos=MagicMock(x=100), distance=5.0, source='distance')
    assert t.distance == 5.0 and t.source == 'distance'


def test_status_constants() -> None:
    """STATUS 常量值(复用原防卫战同值同义)。"""
    assert BattleOpBase.STATUS_NEED_MOVE == '需要移动'
    assert BattleOpBase.STATUS_NEXT_LEVEL == '进入下层'
    assert BattleOpBase.STATUS_COMPLETE == '通关'
    assert BattleOpBase.STATUS_TO_NEXT_PHASE == '下一阶段'


def test_base_is_abstract() -> None:
    """BattleOpBase._get_auto_battle_op_name 默认 raise NotImplementedError。"""
    with pytest.raises(NotImplementedError):
        BattleOpBase(_make_ctx())._get_auto_battle_op_name()


def test_check_battle_state_default_calls_normal() -> None:
    """_check_battle_state 默认调 ctx.check_battle_state(只 normal)。"""
    ctx = _make_ctx()
    ctx.auto_battle_context.check_battle_state.return_value = True
    op = _ConcreteBattleOp(ctx)
    op.last_screenshot = MagicMock()
    op.last_screenshot_time = 1.0
    result = op._check_battle_state()
    ctx.auto_battle_context.check_battle_state.assert_called_once()
    _, kwargs = ctx.auto_battle_context.check_battle_state.call_args
    assert kwargs.get('check_battle_end_normal_result') is True
    assert result is True


def test_move_one_step_turn_when_off_center() -> None:
    """_move_one_step: target.pos.x 偏离中心 > 阈值 → turn_by_distance,不 move_w。"""
    ctx = _make_ctx()
    op = _ConcreteBattleOp(ctx)
    target = MoveTarget(pos=MagicMock(x=200), distance=5.0, source='distance')  # 200 - 960 = -760, abs > 50
    op._move_one_step(target, cap=4)
    ctx.controller.turn_by_distance.assert_called_once()
    ctx.controller.move_w.assert_not_called()


def test_move_one_step_move_when_centered() -> None:
    """_move_one_step: 居中 → move_w(press=True, press_time=distance/7.2 capped)。"""
    ctx = _make_ctx()
    op = _ConcreteBattleOp(ctx)
    target = MoveTarget(pos=MagicMock(x=970), distance=7.2, source='distance')  # 970-960=10 < 50
    op._move_one_step(target, cap=4)
    ctx.controller.move_w.assert_called_once()
    _, kwargs = ctx.controller.move_w.call_args
    assert kwargs.get('press') is True
    assert abs(kwargs.get('press_time') - 1.0) < 0.01  # 7.2/7.2=1.0


def test_move_one_step_none_calls_on_no_target() -> None:
    """_move_one_step(None) → _on_no_target 盲转,不崩。"""
    ctx = _make_ctx()
    op = _ConcreteBattleOp(ctx)
    op._move_one_step(None)  # 不应抛异常
    ctx.controller.turn_by_distance.assert_called_once()


def test_node_graph_builds_without_error() -> None:
    """_ConcreteBattleOp 继承基类节点图,初始化节点图构建不抛异常(节点 + 边注册)。"""
    op = _ConcreteBattleOp(_make_ctx())
    op._init_before_execute()
    # 框架 _node_map: dict[str, OperationNode],值是 OperationNode(直接 .cn)
    node_cns = {n.cn for n in op._node_map.values()}
    assert '加载自动战斗指令' in node_cns
    assert '自动战斗' in node_cns
