"""LostVoidApp.check_predefined_team 测试。

按 testing methodology 动作一:
- ``check_predefined_team``:按 ``mission_name`` / ``choose_team_by_priority`` /
  ``complete_task_force_with_up`` / ``up_team_auto_compose`` / ``predefined_team_idx`` /
  priority 匹配结果,路由到「需选择预备编队」/「无需选择预备编队」,
  并设置 ``use_priority_agent`` + ``ctx.lost_void.predefined_team_idx``。
- UP匹配失败(编队没配 / 编队里没UP)时按固定编队出战,
  **不设置 use_priority_agent**(否则通关后误标记本周已用UP)。
- ``up_team_auto_compose`` 开启时先走 ``LostVoidComposeUpTeam`` 自动配队,
  成功 → 无需选择预备编队;失败 → 回退预备编队匹配。

纯配置/mock 测试,无画面依赖:mock ``team_config.team_list`` 构造可控配队,
``priority_agent_list`` 用 ``AgentEnum.X.value`` 构造,自动配队 op 用 mock 替身。

``LostVoidApp`` 实例化可行(同 test_app_bounty_commission)。
"""
from types import SimpleNamespace
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
    test_context.lost_void.challenge_config.up_team_auto_compose = False
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


# ===== 预备编队匹配 =====


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


def test_no_priority_match_falls_back_without_flag(test_context: TestContext) -> None:
    """priority 无匹配 + 固定编队=2 → 需选择固定编队,但 use_priority 必须为 False。

    原实现无匹配时也置 use_priority=True,通关后误标记「本周已用UP完成」,
    本周内配好编队也不再尝试。
    """
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = True
    test_context.lost_void.challenge_config.predefined_team_idx = 2
    op.run_record.complete_task_force_with_up = False
    mock_teams = [
        _make_team(0, '编队A', ['anby', 'billy', 'unknown']),
        _make_team(1, '编队B', ['grace', 'unknown', 'unknown']),
    ]
    op.priority_agent_list = [AgentEnum.ELLEN.value]  # ellen 不在任何 team
    with patch.object(type(test_context.team_config), 'team_list',
                      new=mock_teams):
        result = op.check_predefined_team()
    assert result.status == '需选择预备编队'
    assert test_context.lost_void.predefined_team_idx == 2
    assert op.use_priority_agent is False, '无UP匹配时不能标记使用了UP'


def test_special_investigation_no_priority_match(test_context: TestContext) -> None:
    """特遣调查 + choose_by_priority=True + priority 无匹配(predefined=-1)→ 无需选择。"""
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = True
    op.run_record.complete_task_force_with_up = False
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


# ===== UP自动配队分支 =====


def test_auto_compose_success_skips_team_select(test_context: TestContext) -> None:
    """up_team_auto_compose=True + 配队 op 成功 → 无需选择预备编队 + use_priority=True。"""
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = True
    test_context.lost_void.challenge_config.up_team_auto_compose = True
    op.run_record.complete_task_force_with_up = False
    mock_teams = [_make_team(0, '编队A', ['ellen', 'anby', 'unknown'])]
    op.priority_agent_list = [AgentEnum.ELLEN.value]
    with (patch.object(type(test_context.team_config), 'team_list', new=mock_teams),
          patch('zzz_od.application.hollow_zero.lost_void.lost_void_app.LostVoidComposeUpTeam') as mock_op_cls):
        mock_op_cls.return_value.execute.return_value = SimpleNamespace(success=True, status='配队完成')
        result = op.check_predefined_team()
    assert result.status == '无需选择预备编队'
    assert op.use_priority_agent is True
    assert mock_op_cls.called


def test_auto_compose_fail_falls_back_to_team_match(test_context: TestContext) -> None:
    """up_team_auto_compose=True + 配队 op 失败 → 回退预备编队匹配(命中编队B)。"""
    op = _setup_op(test_context)
    op.config.mission_name = '特遣调查'
    test_context.lost_void.challenge_config.choose_team_by_priority = True
    test_context.lost_void.challenge_config.up_team_auto_compose = True
    op.run_record.complete_task_force_with_up = False
    mock_teams = [
        _make_team(0, '编队A', ['anby', 'billy', 'unknown']),
        _make_team(1, '编队B', ['ellen', 'unknown', 'unknown']),
    ]
    op.priority_agent_list = [AgentEnum.ELLEN.value]
    with (patch.object(type(test_context.team_config), 'team_list', new=mock_teams),
          patch('zzz_od.application.hollow_zero.lost_void.lost_void_app.LostVoidComposeUpTeam') as mock_op_cls):
        mock_op_cls.return_value.execute.return_value = SimpleNamespace(success=False, status='配队校验失败')
        result = op.check_predefined_team()
    assert result.status == '需选择预备编队'
    assert test_context.lost_void.predefined_team_idx == 1
    assert op.use_priority_agent is True
