"""LostVoidChooseGear 入口层重复交互快速退出测试。

背景(源码 ``lost_void_choose_gear.py``):迷失之地入口层有多个相邻NPC(蕾/奥菲莉亚/研究员),
游戏交互判定按 角度>距离,刚选完武备的NPC仍可重复交互;寻路走向旁边感叹号时容易再次命中
同一个NPC,重复打开同一个武备选择画面(整套点击识别约40秒),累计导致层间移动10分钟超时。

修复行为(已读源码确认):
- 构造时可传 ``completed_name_list``(入口层跨交互共享的**各已完成画面首个武备名**);
  列表非空时,``choose_gear`` 先只点击首个武备读名字(``_get_first_gear_name``),
  difflib(cutoff=0.8,只容忍同名OCR错字) 命中列表 → ``round_success('重复武备选择')``
  → ``重复退出`` 节点点返回后透传该状态。
- 判断信号与存储信号对称(都是画面**最左侧槽位**的武备名):``get_gear_pos_by_click_ocr``
  从槽位0的OCR文本解析 ``first_slot_gear_name``(解析失败为 None);``点击携带`` 成功后
  只把它补进共享列表(去重),不存非首个武备名 也不存"第一个解析成功"的错位名字,
  避免其他画面的首个武备与本画面的非首个武备误匹配(review 反馈两轮修正)。
- 名单已有 2 个武备名(入口层只有两个武备NPC,都完成过)时,再进武备画面必为重复,
  不点首格不读名直接退出(2026-08-26 提速)。
- 列表为 ``None``(层中武备选择)不做快速判断,行为与原来一致。

fixture:``迷失之地-武备选择/初始战术棱镜方案``(已有) 用于画面识别;武备槽位识别与
名称OCR 分别 patch ``_find_gears_with_status`` / ``_get_first_gear_name``,只测决策逻辑。
"""
from difflib import SequenceMatcher
from unittest.mock import Mock, patch

import pytest
from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_gear import (
    LostVoidChooseGear,
)


def _make_op(test_context: TestContext, completed_name_list: list[str] | None) -> LostVoidChooseGear:
    test_context.lost_void.load_artifact_data()
    op = LostVoidChooseGear(test_context, completed_name_list=completed_name_list)
    test_context.mock_screen('迷失之地-武备选择', '初始战术棱镜方案')
    op.screenshot()
    return op


# (已完成名单, 首个武备OCR名, 期望命中)
# difflib cutoff=0.8:同名/单字OCR错字仍命中(比值≈0.875);相似但不同的武备名不命中
# (「敕令玄幡」vs「敕令令旗」比值 0.75,落在 0.7~0.8 之间 —— cutoff=0.7 会误判,0.8 不会)
# 名单固定单元素:两个武备都完成后走"必为重复"捷径不再读名(见下方专项用例)
QUICK_CHECK_CASES: list[tuple[list[str], str, bool]] = [
    (['[携游]敕令玄幡'], '[携游]敕令玄幡', True),
    (['[携游]敕令玄幡'], '[携游]敕令玄蟠', True),  # OCR 错一字
    (['[携游]敕令玄幡'], '[携游]敕令令旗', False),  # 相似度≈0.75 的不同武备 不误判
    (['[携游]敕令玄幡'], '[照]月魄凛光', False),  # 另一个NPC的武备画面 不命中
]


def test_quick_check_case_ratio_assumptions() -> None:
    """守住用例的相似度前提:错字对 ≥0.8(应命中);相近不同对 在 0.7~0.8(0.8 下不命中)。"""
    typo_ratio = SequenceMatcher(None, '[携游]敕令玄幡', '[携游]敕令玄蟠').ratio()
    similar_ratio = SequenceMatcher(None, '[携游]敕令玄幡', '[携游]敕令令旗').ratio()
    assert typo_ratio >= 0.8, f'错字对比值 {typo_ratio:.3f} 应 ≥0.8'
    assert 0.7 <= similar_ratio < 0.8, f'相近对比值 {similar_ratio:.3f} 应落在 0.7~0.8'


@pytest.mark.parametrize(
    'completed, first_name, expect_hit', QUICK_CHECK_CASES,
    ids=['同名命中', '错字命中', '相近不同不误判', '不同画面不命中'],
)
def test_quick_check_by_first_gear_name(
    test_context: TestContext, completed: list[str], first_name: str, expect_hit: bool,
) -> None:
    """列表非空时按首个武备名快速判断:命中 → 重复武备选择;不命中 → 继续原有识别流程。"""
    op = _make_op(test_context, completed)

    with (
        patch.object(test_context.controller, 'mouse_move', create=True),
        patch.object(op, '_find_gears_with_status', return_value=([(object(), True)], object())),
        patch.object(op, '_get_first_gear_name', return_value=first_name),
        patch.object(op, 'get_gear_pos_by_click_ocr', return_value=([], [])) as mock_full_ocr,
    ):
        result = op.choose_gear()

    if expect_hit:
        assert result.is_success
        assert result.status == LostVoidChooseGear.STATUS_REPEATED
        assert not mock_full_ocr.called, '命中重复后不应再执行整套点击识别'
    else:
        # 不命中 → 走原有流程(此处 get_gear_pos_by_click_ocr 返回空 → round_retry)
        assert mock_full_ocr.called, '不命中时应继续原有识别流程'
        assert not result.is_success


def test_two_completed_gears_short_circuits_without_reading(test_context: TestContext) -> None:
    """名单已有2个武备名(入口层两个武备NPC都完成)→ 必为重复 不点首格不读名直接退出。"""
    op = _make_op(test_context, ['[携游]敕令玄幡', '[照]月魄凛光'])

    with (
        patch.object(test_context.controller, 'mouse_move', create=True),
        patch.object(op, '_find_gears_with_status') as mock_find,
        patch.object(op, '_get_first_gear_name') as mock_quick,
    ):
        result = op.choose_gear()

    assert result.is_success
    assert result.status == LostVoidChooseGear.STATUS_REPEATED
    assert not mock_find.called, '两武备均完成时连槽位识别都不需要'
    assert not mock_quick.called, '两武备均完成时不需要点首格读名'


def test_none_completed_list_skips_quick_check(test_context: TestContext) -> None:
    """completed_name_list 为 None(层中武备选择)时 不做快速判断。"""
    op = _make_op(test_context, None)

    with (
        patch.object(test_context.controller, 'mouse_move', create=True),
        patch.object(op, '_find_gears_with_status', return_value=([(object(), True)], object())),
        patch.object(op, '_get_first_gear_name') as mock_quick,
        patch.object(op, 'get_gear_pos_by_click_ocr', return_value=([], [])),
    ):
        op.choose_gear()

    assert not mock_quick.called, 'None 时不应执行快速判断'


def test_empty_completed_list_skips_quick_check(test_context: TestContext) -> None:
    """列表为空(入口层第一次选择)时 不做快速判断,直接走原有流程。"""
    op = _make_op(test_context, [])

    with (
        patch.object(test_context.controller, 'mouse_move', create=True),
        patch.object(op, '_find_gears_with_status', return_value=([(object(), True)], object())),
        patch.object(op, '_get_first_gear_name') as mock_quick,
        patch.object(op, 'get_gear_pos_by_click_ocr', return_value=([], [])),
    ):
        op.choose_gear()

    assert not mock_quick.called, '空列表(首次)不应执行快速判断'


def test_first_slot_name_not_replaced_by_next_parsed_slot(test_context: TestContext) -> None:
    """最左格OCR解析失败时 first_slot_gear_name 为 None 而不是顺延取下一个解析成功的槽位。"""
    test_context.lost_void.load_artifact_data()
    op = LostVoidChooseGear(test_context, completed_name_list=[])

    # 槽位0解析失败(无[分类]名称结构) 槽位1解析成功 → 不应把槽位1当作最左格
    op._update_first_slot_gear_name(['???', '[携游]敕令玄幡'])
    assert op.first_slot_gear_name is None, '最左格解析失败时不应顺延取后面槽位'

    op._update_first_slot_gear_name(['[携游]敕令玄幡', '[终结]律动节能器'])
    assert op.first_slot_gear_name == '[携游]敕令玄幡'

    op._update_first_slot_gear_name([])
    assert op.first_slot_gear_name is None


def test_click_equip_commits_first_slot_name(test_context: TestContext) -> None:
    """点击携带成功后 只把最左侧槽位武备名补进共享列表(与判断信号对称)。"""
    shared: list[str] = ['[照]月魄凛光']
    op = LostVoidChooseGear(test_context, completed_name_list=shared)
    op.first_slot_gear_name = '[携游]敕令玄幡'

    success = op.round_success('按钮-携带')
    with patch.object(op, 'round_by_find_and_click_area', return_value=success):
        op.click_equip()

    assert shared == ['[照]月魄凛光', '[携游]敕令玄幡'], '只应追加最左侧槽位武备名'


def test_click_equip_dedupes_first_slot_name(test_context: TestContext) -> None:
    """最左侧槽位武备名已在共享列表时 不重复添加。"""
    shared: list[str] = ['[携游]敕令玄幡']
    op = LostVoidChooseGear(test_context, completed_name_list=shared)
    op.first_slot_gear_name = '[携游]敕令玄幡'

    success = op.round_success('按钮-携带')
    with patch.object(op, 'round_by_find_and_click_area', return_value=success):
        op.click_equip()

    assert shared == ['[携游]敕令玄幡'], '重复的武备名不应再次添加'


def test_click_equip_skips_when_first_slot_unparsed(test_context: TestContext) -> None:
    """最左侧槽位OCR解析失败(first_slot_gear_name=None)时 本画面不记录 不写入错位名字。"""
    shared: list[str] = ['[照]月魄凛光']
    op = LostVoidChooseGear(test_context, completed_name_list=shared)
    op.first_slot_gear_name = None

    success = op.round_success('按钮-携带')
    with patch.object(op, 'round_by_find_and_click_area', return_value=success):
        result = op.click_equip()

    assert result.is_success
    assert shared == ['[照]月魄凛光'], '最左格解析失败时不应写入任何名字'


def test_click_equip_without_shared_list(test_context: TestContext) -> None:
    """completed_name_list 为 None 时 点击携带不报错(层中武备选择场景)。"""
    op = LostVoidChooseGear(test_context, completed_name_list=None)
    op.first_slot_gear_name = '[携游]敕令玄幡'

    success = op.round_success('按钮-携带')
    with patch.object(op, 'round_by_find_and_click_area', return_value=success):
        result = op.click_equip()

    assert result.is_success


def test_exit_repeated_clicks_back_and_returns_status(test_context: TestContext) -> None:
    """重复退出节点:点击返回成功后 以 重复武备选择 状态结束(供 run_level 计数)。"""
    op = LostVoidChooseGear(test_context, completed_name_list=['[携游]敕令玄幡'])

    success = op.round_success('按钮-返回')
    with patch.object(op, 'round_by_find_and_click_area', return_value=success) as mock_click:
        result = op.exit_repeated()

    assert mock_click.called
    assert result.is_success
    assert result.status == LostVoidChooseGear.STATUS_REPEATED
