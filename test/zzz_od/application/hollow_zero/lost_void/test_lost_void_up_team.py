"""迷失之地 UP自动配队 lost_void_up_team 测试。

- ``compute_up_lineup``:配队规则(已拥有UP全上 / 同队搭档补位 / 无UP试用保底)。纯数据。
- ``recognize_matrix_up`` / ``find_up_in_agent_grid``:真实 fixture 识别
  (矩阵入口UP头像行 / 编队选择网格UP徽章;2026-08-21 实拍,当期UP:
  特遣=蕾米埃尔/维琳娜/爱丽丝,矩阵主战=蕾米埃尔+维琳娜(试用)、协战=妮可)。
- ``LostVoidComposeUpTeam``:出战画面槽位名字OCR读队 + 换人计划。真实 fixture。

fixture 不存在时 skip(采到后自动恢复,见 conftest.has_screen)。
"""
import pytest

from test.conftest import TestContext

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_up_team import (
    LostVoidComposeUpTeam,
    compute_up_lineup,
    find_up_in_agent_grid,
    recognize_matrix_up,
)
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.game_data.agent import AgentEnum

# 编队选择画面「代理人列表」区域(与 screen_info 一致)
MATRIX_AGENT_GRID_RECT = Rect(185, 96, 966, 1059)


def _team(agent_ids: list[str]) -> PredefinedTeamInfo:
    return PredefinedTeamInfo(0, '编队', '全配队通用', agent_ids)


def _agents(*names: str) -> list:
    by_name = {e.value.agent_name: e.value for e in AgentEnum}
    return [by_name[n] for n in names]


# ===== compute_up_lineup =====


def test_lineup_owned_up_plus_co_partner() -> None:
    """已拥有UP全上,搭档按同队次数补(爱丽丝+蕾米埃尔 → 补共同队友薇薇安)。"""
    up = _agents('蕾米埃尔', '维琳娜', '爱丽丝')
    teams = [
        _team(['yuzuha', 'alice', 'vivian']),
        _team(['promeia', 'vivian', 'remielle']),
        _team(['nicole', 'billy', 'unknown']),
    ]
    lineup = compute_up_lineup(up, teams, 3)
    assert {a.agent_name for a in lineup} == {'蕾米埃尔', '爱丽丝', '薇薇安'}


def test_lineup_no_owned_up_uses_first_up() -> None:
    """一个UP都没拥有:用第一个UP保底 + 高频队友补位。"""
    up = _agents('维琳娜')
    teams = [
        _team(['nicole', 'billy', 'unknown']),
        _team(['nicole', 'ellen', 'unknown']),
    ]
    lineup = compute_up_lineup(up, teams, 3)
    names = [a.agent_name for a in lineup]
    assert names[0] == '维琳娜'
    assert '妮可' in names and len(lineup) == 3


def test_lineup_excludes_unowned_up_from_partners() -> None:
    """未拥有的UP不能被当成搭档补进来。"""
    up = _agents('蕾米埃尔', '维琳娜')
    teams = [_team(['remielle', 'vivian', 'unknown'])]
    lineup = compute_up_lineup(up, teams, 3)
    names = [a.agent_name for a in lineup]
    assert '维琳娜' not in names
    assert '蕾米埃尔' in names and '薇薇安' in names


# ===== 真实 fixture 识别 =====


def test_recognize_matrix_up_entry_panel(test_context: TestContext) -> None:
    """矩阵入口面板UP头像行:协战识别为妮可(带协战标签/最右),主战含蕾米埃尔。"""
    if not test_context.has_screen('迷失之地-矩阵行动', '入口面板'):
        pytest.skip('缺 fixture: 迷失之地-矩阵行动/入口面板')
    screen = test_context.load_screen('迷失之地-矩阵行动', '入口面板')
    mains, support = recognize_matrix_up(test_context, screen)
    assert '妮可' in [a.agent_name for a in support]
    assert '蕾米埃尔' in [a.agent_name for a in mains]


def test_find_up_in_agent_grid(test_context: TestContext) -> None:
    """编队选择网格UP徽章:关联到维琳娜(2026-08-21 实拍徽章唯一OCR命中)。"""
    if not test_context.has_screen('迷失之地-矩阵行动-编队选择', '自由编队-初始'):
        pytest.skip('缺 fixture: 迷失之地-矩阵行动-编队选择/自由编队-初始')
    screen = test_context.load_screen('迷失之地-矩阵行动-编队选择', '自由编队-初始')
    up_list = find_up_in_agent_grid(test_context, screen, MATRIX_AGENT_GRID_RECT)
    assert '维琳娜' in [a.agent_name for a in up_list]


# ===== LostVoidComposeUpTeam 读队/计划 =====


def _make_compose_op(test_context: TestContext, state: str) -> LostVoidComposeUpTeam:
    lineup = _agents('蕾米埃尔', '爱丽丝', '薇薇安')
    up_ids = {a.agent_id for a in _agents('蕾米埃尔', '维琳娜', '爱丽丝')}
    op = LostVoidComposeUpTeam(test_context, lineup, up_ids)
    test_context.mock_screen('通用-出战', state)
    op.screenshot()
    return op


def test_read_current_member_ids_full_team(test_context: TestContext) -> None:
    """出战画面槽位名字OCR:妮可/比利/爱丽丝。"""
    if not test_context.has_screen('通用-出战', '特遣调查-编队-满员含UP'):
        pytest.skip('缺 fixture: 通用-出战/特遣调查-编队-满员含UP')
    op = _make_compose_op(test_context, '特遣调查-编队-满员含UP')
    assert op._read_current_member_ids() == ['nicole', 'billy', 'alice']


def test_plan_with_empty_slot(test_context: TestContext) -> None:
    """当前 妮可/比利/空 vs 目标 蕾米埃尔/爱丽丝/薇薇安 → 三个槽位都要换。"""
    if not test_context.has_screen('通用-出战', '特遣调查-编队-有空位'):
        pytest.skip('缺 fixture: 通用-出战/特遣调查-编队-有空位')
    op = _make_compose_op(test_context, '特遣调查-编队-有空位')
    result = op.check_current_team()
    assert result.status == '需调整'
    assert len(op.plan) == 3
    assert [slot for slot, _ in op.plan] == [0, 1, 2]


# ===== 拿不到UP时提前收手 =====


def _make_plain_op(test_context: TestContext, lineup_names: list[str],
                   up_names: list[str]) -> LostVoidComposeUpTeam:
    """不依赖画面 只测 _can_still_get_up 的判断。"""
    return LostVoidComposeUpTeam(
        test_context, _agents(*lineup_names), {a.agent_id for a in _agents(*up_names)})


def test_can_still_get_up_when_up_left_in_plan(test_context: TestContext) -> None:
    """计划里还有没试过的UP → 继续换下去。"""
    op = _make_plain_op(test_context, ['蕾米埃尔', '爱丽丝', '薇薇安'], ['蕾米埃尔', '爱丽丝'])
    op.plan = list(zip([0, 1, 2], op.lineup, strict=False))
    op.plan_idx = 1  # 槽位0的蕾米埃尔没找到 但爱丽丝还没试
    assert op._can_still_get_up() is True


def test_can_not_get_up_after_all_up_missed(test_context: TestContext) -> None:
    """UP都试过且都没找到 原编队也没有UP → 不再动剩余槽位。"""
    op = _make_plain_op(test_context, ['蕾米埃尔', '爱丽丝', '薇薇安'], ['蕾米埃尔', '爱丽丝'])
    op.plan = list(zip([0, 1, 2], op.lineup, strict=False))
    op.plan_idx = 2  # 只剩搭档薇薇安
    assert op._can_still_get_up() is False


def test_can_still_get_up_when_original_team_has_up(test_context: TestContext) -> None:
    """原编队自带UP(没被换掉) → 即使目标UP没找到也还算数。"""
    op = _make_plain_op(test_context, ['蕾米埃尔', '爱丽丝', '薇薇安'], ['蕾米埃尔', '爱丽丝'])
    op.plan = list(zip([0, 1, 2], op.lineup, strict=False))
    op.plan_idx = 2
    op.kept_up = True
    assert op._can_still_get_up() is True


def test_can_still_get_up_after_placed(test_context: TestContext) -> None:
    """已经换入过UP → 后面搭档找不到也不影响。"""
    op = _make_plain_op(test_context, ['蕾米埃尔', '爱丽丝', '薇薇安'], ['蕾米埃尔', '爱丽丝'])
    op.plan = list(zip([0, 1, 2], op.lineup, strict=False))
    op.plan_idx = 2
    op.placed = _agents('蕾米埃尔')
    assert op._can_still_get_up() is True


# ===== 换人计划: 搭档不顶掉当前持有UP的槽位 =====


def _make_planned_op(test_context: TestContext, current_names: list[str | None],
                     lineup_names: list[str], up_names: list[str]) -> LostVoidComposeUpTeam:
    """打桩槽位读取 只测 check_current_team 的计划生成。"""
    op = LostVoidComposeUpTeam(
        test_context, _agents(*lineup_names), {a.agent_id for a in _agents(*up_names)})
    current_ids = [(_agents(n)[0].agent_id if n is not None else None) for n in current_names]
    op._read_current_member_ids = lambda: current_ids
    return op


def test_plan_partner_never_replaces_up_slot(test_context: TestContext) -> None:
    """队里已有不在目标配队里的UP(试用维琳娜) → 搭档只配到非UP槽位 维琳娜留下 多出的搭档放弃。
    否则UP换入失败时 kept_up 依据的维琳娜会被换搭档顶掉 队里反而没UP。"""
    op = _make_planned_op(test_context, ['妮可', '维琳娜', '比利'],
                          ['蕾米埃尔', '薇薇安', '普罗米娅'], ['蕾米埃尔', '维琳娜', '爱丽丝'])
    result = op.check_current_team()
    assert result.status == '需调整'
    assert op.kept_up is True
    assert [(slot, agent.agent_name) for slot, agent in op.plan] == [(0, '蕾米埃尔'), (2, '薇薇安')]


def test_plan_up_may_replace_up_slot(test_context: TestContext) -> None:
    """非UP槽位不够时 多出来的目标UP才允许换掉队里的UP(艾莲保留 蕾米埃尔换妮可 爱丽丝换维琳娜)。"""
    op = _make_planned_op(test_context, ['维琳娜', '妮可', '艾莲'],
                          ['蕾米埃尔', '爱丽丝', '艾莲'], ['蕾米埃尔', '维琳娜', '爱丽丝'])
    result = op.check_current_team()
    assert result.status == '需调整'
    assert [(slot, agent.agent_name) for slot, agent in op.plan] == [(1, '蕾米埃尔'), (0, '爱丽丝')]
