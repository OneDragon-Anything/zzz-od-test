"""MoveTargetWrapper 纯逻辑测试(合并入口矩形)。

源码在 ``lost_void_move_by_det.py``。``MoveTargetWrapper`` 包装一个 YOLO 检测结果,
``merge_another_target`` 按「两 rect 中心距离 < rect.width*2」判定是否合并,合并后:
- 双方 is_mixed=True,被合并方 merge_parent 指向合并方;
- 名称/矩形列表 extend,entire_rect 取并集,leftest_target_name 取最左(x1 最小)的名称。

已混合(is_mixed=True 且 merge_parent 非空)的节点再次参与合并时,会先解引用到其
merge_parent 再参与判定(避免重复/丢失)。
"""
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.yolo.detect_utils import DetectClass, DetectObjectResult
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    MoveTargetWrapper,
)


def _make_wrapper(
    x1: int, y1: int, x2: int, y2: int, name: str = '入口',
) -> MoveTargetWrapper:
    """构造一个 MoveTargetWrapper。

    class_name 形如 ``xxxx-入口``(5 字符前缀 + 中文名),与 LostVoidDetector 约定一致;
    ``__init__`` 取 ``class_name[5:]`` 作为目标名。
    """
    dr = DetectObjectResult(
        rect=[x1, y1, x2, y2], score=1.0,
        detect_class=DetectClass(class_id=0, class_name=f'xxxx-{name}'),
    )
    return MoveTargetWrapper(dr)


def test_init_state() -> None:
    """初始化:单元素列表,entire_rect 为自身,未混合,无父节点。"""
    w = _make_wrapper(100, 100, 200, 200, '入口')
    assert w.is_mixed is False
    assert w.merge_parent is None
    assert w.target_name_list == ['入口']
    assert w.leftest_target_name == '入口'
    assert w.entire_rect == Rect(100, 100, 200, 200)
    assert len(w.target_rect_list) == 1


def test_merge_close_rects() -> None:
    """两 rect 中心距离 < width*2 -> 合并成功,双方 mixed,父节点/并集/最左名正确。

    a: (100,100,200,200) width=100 center=(150,150)
    b: (220,100,320,200) width=100 center=(270,150)
    距离 120 < 200 -> 合并。
    """
    a = _make_wrapper(100, 100, 200, 200, '入口')
    b = _make_wrapper(220, 100, 320, 200, '战斗-道中危机')

    assert a.merge_another_target(b) is True
    # 双方均标记混合,b 的父节点是 a
    assert a.is_mixed is True
    assert b.is_mixed is True
    assert b.merge_parent is a
    # 列表已 extend
    assert a.target_name_list == ['入口', '战斗-道中危机']
    assert len(a.target_rect_list) == 2
    # entire_rect 取并集
    assert a.entire_rect == Rect(100, 100, 320, 200)
    # 最左(x1 最小)的名称:a 的 x1=100 < b 的 x1=220 -> '入口'
    assert a.leftest_target_name == '入口'


def test_merge_far_rects() -> None:
    """两 rect 中心距离 >= width*2 -> 不合并,双方保持原状。

    c: (100,100,200,200) center=(150,150) width=100
    d: (500,100,600,200) center=(550,150) width=100
    距离 400 > 200 -> 不合并。
    """
    c = _make_wrapper(100, 100, 200, 200, '入口')
    d = _make_wrapper(500, 100, 600, 200, '战斗-道中危机')

    assert c.merge_another_target(d) is False
    assert c.is_mixed is False
    assert d.is_mixed is False
    assert d.merge_parent is None
    assert c.target_name_list == ['入口']
    assert c.entire_rect == Rect(100, 100, 200, 200)


def test_merge_dereferences_other_parent() -> None:
    """被合并方(is_mixed=True 且有父节点)参与合并时,实际并入其父节点。

    场景:
    1. e.merge(g) -> e 是父,g.merge_parent=e,e 含 [入口, 战斗-道中危机]
    2. f.merge(g) -> 因 g 已混合且 merge_parent=e,实际 other 解引用为 e
       f(250,150,350,250) center=(300,200) 与 e 的 rect 之一中心距 < width*2 -> 合并
       合并后 this=f, other=e -> e.merge_parent=f,f 成为新父节点
    """
    e = _make_wrapper(100, 100, 200, 200, '入口')
    g = _make_wrapper(220, 100, 320, 200, '战斗-道中危机')
    assert e.merge_another_target(g) is True
    assert g.merge_parent is e

    f = _make_wrapper(250, 150, 350, 250, '挑战-限时')
    assert f.merge_another_target(g) is True
    # f 成为新的父节点(merge_parent 保持 None),e 反向指向 f
    assert f.merge_parent is None
    assert e.merge_parent is f
    # f 的名称列表包含 e 累积的全部名称
    assert '挑战-限时' in f.target_name_list
    assert '入口' in f.target_name_list
    assert '战斗-道中危机' in f.target_name_list


def test_merge_dereferences_self_parent() -> None:
    """合并方(is_mixed=True 且有父节点)参与合并时,this 解引用到其父节点。

    场景:
    1. p.merge(c1) -> p 父,c1.merge_parent=p
    2. c1.merge(c2) -> c1 已混合,实际 this=p;c2 与 p 的 rect 近 -> 合并到 p
       合并后 c2.merge_parent=p(而非 c1)
    """
    p = _make_wrapper(100, 100, 200, 200, '入口')
    c1 = _make_wrapper(220, 100, 320, 200, '战斗-道中危机')
    assert p.merge_another_target(c1) is True

    c2 = _make_wrapper(340, 100, 440, 200, '挑战-限时')
    # c1 已是 p 的子节点,再由 c1 发起合并 -> 实际并入 p
    assert c1.merge_another_target(c2) is True
    # c2 的父节点是 p(c1 解引用后的 this),不是 c1
    assert c2.merge_parent is p
    # p 累积了三个名称
    assert len(p.target_name_list) == 3
    assert '挑战-限时' in p.target_name_list
