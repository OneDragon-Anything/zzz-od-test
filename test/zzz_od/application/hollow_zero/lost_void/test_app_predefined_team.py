"""LostVoidApp.check_predefined_team + get_target_team_idx_by_priority 测试。

按 testing methodology 动作一:
- ``check_predefined_team``:按 ``mission_name`` / ``choose_team_by_priority`` /
  ``complete_task_force_with_up`` / ``predefined_team_idx`` / priority 匹配结果,
  路由到「需选择预备编队」/「无需选择预备编队」,并设置 ``use_priority_agent`` +
  ``ctx.lost_void.predefined_team_idx``。
- ``get_target_team_idx_by_priority``:遍历 ``team_config.team_list`` ×
  ``priority_agent_list`` → 匹配数最多的 idx;都不匹配返 ``predefined_team_idx``。

纯配置/mock 测试,无画面依赖:mock ``team_config.team_list`` 构造可控配队,
``priority_agent_list`` 用 ``AgentEnum.X.value`` 构造。

``LostVoidApp`` 实例化可行(同 test_app_bounty_commission)。
"""
from unittest.mock import patch

from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.lost_void_app import LostVoidApp
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.game_data.agent import AgentEnum


def _setup_op(test_context: TestContext) -> LostVoidApp:
    """构造 LostVoidApp 实例并重置挑战/优先级相关配置。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    test_context.lost_void.challenge_config.choose_team_by_priority = False
    test_context.lost_void.challenge_config.predefined_team_idx = -1
    test_context.lost_void.predefined_team_idx = -1
    return LostVoidApp(
        test_context,
        lost_void_debug=False,
        next_region_type=LostVoidRegionType.ENTRY,
    )


def _make_team(idx: int, name: str, agent_ids: list[str]) -> PredefinedTeamInfo:
    """构造一个 PredefinedTeamInfo 用于 mock team_list。"""
    return PredefinedTeamInfo(idx, name, '全配队通用', agent_ids)


# ===== get_target_team_idx_by_priority 测试 =====


def test_priority_match_returns_best_team_idx(test_context: TestContext) -> None:
    """priority_agent_list 命中 team[1] 最多代理人 → 返回 idx=1。"""
    op = _setup_op(test_context)
    mock_teams = [
        _make_team(0, '编队A', ['anby', 'billy', 'unknown']),
        _make_team(1, '编队B', ['ellen', 'anby', 'unknown']),
        _make_team(2, '编队C', ['grace', 'unknown', 'unknown']),
    ]
    op.priority_agent_list = [AgentEnum.ELLEN.value, AgentEnum.ANBY.value]
    with patch.object(type(test_context.team_config), 'team_list',
                      new=mock_teams):
        idx = op.get_target_team_idx_by_priority()
    assert idx == 1, 'team[1] 命中 ellen + anby(2 个),应返回 1'


def test_no_priority_match_returns_predefined_idx(test_context: TestContext) -> None:
    """priority_agent_list 都不匹配 → 返回 challenge_config.predefined_team_idx。"""
    op = _setup_op(test_context)
    test_context.lost_void.challenge_config.predefined_team_idx = 2
    mock_teams = [
        _make_team(0, '编队A', ['anby', 'billy', 'unknown']),
        _make_team(1, '编队B', ['grace', 'unknown', 'unknown']),
    ]
    op.priority_agent_list = [AgentEnum.ELLEN.value]  # ellen 不在任何 team
    with patch.object(type(test_context.team_config), 'team_list',
                      new=mock_teams):
        idx = op.get_target_team_idx_by_priority()
    assert idx == 2, '无匹配应返回 predefined_team_idx=2'


def test_priority_default_predefined_idx_is_minus_one(test_context: TestContext) -> None:
    """无匹配且 predefined_team_idx=-1 → 返回 -1。"""
    op = _setup_op(test_context)
    mock_teams = [_make_team(0, '编队A', ['anby', 'billy', 'unknown'])]
    op.priority_agent_list = [AgentEnum.ELLEN.value]
    with patch.object(type(test_context.team_config), 'team_list',
                      new=mock_teams):
        idx = op.get_target_team_idx_by_priority()
    assert idx == -1


# ===== check_predefined_team 测试 =====


def test_special_investigation_priority_match(test_context: TestContext) -> None:
    """特遣调查 + choose_by_priority=True + 未用过 UP + priority 命中 → 需选择,use_priority=True。"""
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = True
    op.run_record.complete_task_force_with_up = False
    mock_teams = [
        _make_team(0, '编队A', ['anby', 'billy', 'unknown']),
        _make_team(1, '编队B', ['ellen', 'anby', 'unknown']),
    ]
    op.priority_agent_list = [AgentEnum.ELLEN.value, AgentEnum.ANBY.value]
    with patch.object(type(test_context.team_config), 'team_list',
                      new=mock_teams):
        result = op.check_predefined_team()
    assert result.status == '需选择预备编队'
    assert op.use_priority_agent is True
    assert test_context.lost_void.predefined_team_idx == 1


def test_special_investigation_no_priority_match(test_context: TestContext) -> None:
    """特遣调查 + choose_by_priority=True + priority 无匹配(predefined=-1)→ 无需选择。"""
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = True
    op.run_record.complete_task_force_with_up = False
    # predefined_team_idx 已经是 -1,get_target_team_idx_by_priority 无匹配也返 -1
    mock_teams = [_make_team(0, '编队A', ['anby', 'billy', 'unknown'])]
    op.priority_agent_list = [AgentEnum.ELLEN.value]  # 无匹配
    with patch.object(type(test_context.team_config), 'team_list',
                      new=mock_teams):
        result = op.check_predefined_team()
    assert result.status == '无需选择预备编队'
    assert op.use_priority_agent is False


def test_special_investigation_already_used_up(test_context: TestContext) -> None:
    """特遣调查 + choose_by_priority=True + 已用过 UP(complete_task_force_with_up=True)→ 跳过 priority 分支。"""
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = True
    op.run_record.complete_task_force_with_up = True  # 本周已用 UP
    # predefined_team_idx=-1 → fall through 后也是「无需选择」
    result = op.check_predefined_team()
    assert result.status == '无需选择预备编队'
    assert op.use_priority_agent is False


def test_predefined_team_idx_not_minus_one(test_context: TestContext) -> None:
    """challenge_config.predefined_team_idx != -1 → 直接使用,需选择。"""
    op = _setup_op(test_context)
    op.config.mission_name = '战线肃清'  # 非特遣调查
    test_context.lost_void.challenge_config.predefined_team_idx = 2
    result = op.check_predefined_team()
    assert result.status == '需选择预备编队'
    assert test_context.lost_void.predefined_team_idx == 2
    assert op.use_priority_agent is False


def test_no_predefined_team_and_no_priority(test_context: TestContext) -> None:
    """非特遣调查 + predefined_team_idx=-1 → 无需选择。"""
    op = _setup_op(test_context)
    op.config.mission_name = '战线肃清'
    # predefined_team_idx 已是 -1
    result = op.check_predefined_team()
    assert result.status == '无需选择预备编队'
    assert op.use_priority_agent is False


def test_choose_by_priority_false_skips_priority_branch(test_context: TestContext) -> None:
    """特遣调查 + choose_by_priority=False → 跳过 priority 分支,看 predefined_team_idx。"""
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = False
    op.run_record.complete_task_force_with_up = False
    # predefined_team_idx=-1 → 「无需选择」
    result = op.check_predefined_team()
    assert result.status == '无需选择预备编队'
    assert op.use_priority_agent is False
