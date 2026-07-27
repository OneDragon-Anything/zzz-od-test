"""LostVoidChooseCommon 纯逻辑方法测试(sort_candidates / has_priority_rule)。

这两个方法不依赖画面/YOLO,只需 op 实例 + ctx.lost_void 配置。
- sort_candidates:排序 key = (is_primary_name, level_rank, center.x, center.y)。
- has_priority_rule:检查 dynamic_priority_list / artifact_priority / artifact_priority_2 非空。
"""

from test.conftest import TestContext

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import (
    LostVoidArtifact,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import (
    LostVoidArtifactPos,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import (
    LostVoidChooseCommon,
)


def _setup_op(test_context: TestContext) -> LostVoidChooseCommon:
    """加载藏品数据 + 挑战配置,返回 op 实例。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    return LostVoidChooseCommon(test_context)


def _make_pos(
    name: str, level: str, x1: int, is_primary: bool = True, category: str = '异常',
) -> LostVoidArtifactPos:
    """构造最小可用的 LostVoidArtifactPos(rect 宽 10,中心 x = x1+5)。"""
    art = LostVoidArtifact(category=category, name=name, level=level)
    return LostVoidArtifactPos(
        art=art, rect=Rect(x1, 0, x1 + 10, 10), is_primary_name=is_primary,
    )


# ---------------- sort_candidates ----------------

def test_sort_candidates_empty(test_context: TestContext) -> None:
    """空列表 -> 空列表。"""
    op = _setup_op(test_context)
    assert op.sort_candidates([]) == []


def test_sort_candidates_single(test_context: TestContext) -> None:
    """单元素 -> 原样返回。"""
    op = _setup_op(test_context)
    pos = _make_pos('x', 'S', 100)
    assert op.sort_candidates([pos]) == [pos]


def test_sort_candidates_order(test_context: TestContext) -> None:
    """排序优先级:is_primary_name > level(S<A<B) > center.x > center.y。

    构造:
    - pS: primary, S 级, x=100  -> key (0, 0, 105, 5)
    - pA: primary, A 级, x=50   -> key (0, 1, 55, 5)
    - pB_np: 非 primary, B 级    -> key (1, 2, 15, 5)
    期望顺序:[pS, pA, pB_np]
    """
    op = _setup_op(test_context)
    pS = _make_pos('S', 'S', 100, is_primary=True)
    pA = _make_pos('A', 'A', 50, is_primary=True)
    pB_np = _make_pos('B', 'B', 10, is_primary=False)

    result = op.sort_candidates([pB_np, pA, pS])
    assert result == [pS, pA, pB_np]


def test_sort_candidates_level_breaks_tie(test_context: TestContext) -> None:
    """同为 primary 时,按 level 排序:S < A < B。"""
    op = _setup_op(test_context)
    pB = _make_pos('B', 'B', 100, is_primary=True)
    pS = _make_pos('S', 'S', 100, is_primary=True)
    pA = _make_pos('A', 'A', 100, is_primary=True)
    result = op.sort_candidates([pB, pA, pS])
    assert [i.artifact.name for i in result] == ['S', 'A', 'B']


def test_sort_candidates_unknown_level_ranked_last(test_context: TestContext) -> None:
    """未知 level(非 S/A/B)rank=9,排在已知 level 之后。"""
    op = _setup_op(test_context)
    p_known = _make_pos('known', 'B', 100, is_primary=True)
    p_unknown = _make_pos('unk', '?', 100, is_primary=True)
    result = op.sort_candidates([p_unknown, p_known])
    assert result == [p_known, p_unknown]


# ---------------- has_priority_rule ----------------

def _reset_priorities(test_context: TestContext) -> None:
    """把三处优先级来源全部清空,回到「无规则」基线。"""
    test_context.lost_void.dynamic_priority_list = []
    test_context.lost_void.challenge_config.artifact_priority = []
    test_context.lost_void.challenge_config.artifact_priority_2 = []


def test_has_priority_rule_all_empty(test_context: TestContext) -> None:
    """三处优先级来源均空 -> False。"""
    op = _setup_op(test_context)
    _reset_priorities(test_context)
    assert op.has_priority_rule() is False


def test_has_priority_rule_dynamic(test_context: TestContext) -> None:
    """dynamic_priority_list 非空 -> True。"""
    op = _setup_op(test_context)
    _reset_priorities(test_context)
    test_context.lost_void.dynamic_priority_list = ['异常']
    assert op.has_priority_rule() is True


def test_has_priority_rule_priority_1(test_context: TestContext) -> None:
    """artifact_priority 非空 -> True。"""
    op = _setup_op(test_context)
    _reset_priorities(test_context)
    test_context.lost_void.challenge_config.artifact_priority = ['异常']
    assert op.has_priority_rule() is True


def test_has_priority_rule_priority_2(test_context: TestContext) -> None:
    """artifact_priority_2 非空 -> True。"""
    op = _setup_op(test_context)
    _reset_priorities(test_context)
    test_context.lost_void.challenge_config.artifact_priority_2 = ['异常']
    assert op.has_priority_rule() is True
