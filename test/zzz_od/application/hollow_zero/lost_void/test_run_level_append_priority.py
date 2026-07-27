"""LostVoidRunLevel.append_agent_type_priority 代理人类型优先级追加测试。

按 testing methodology 动作一:``append_agent_type_priority`` 读取战斗上下文中的队伍
``agent_list``(Agent.agent_type)+ ``challenge_config`` 的优先级/放弃规则,修改
``ctx.lost_void.dynamic_priority_list`` / ``dynamic_abandon_list``。

纯配置/mock 测试,无画面依赖:
- 用 ``patch.object`` patch 掉 ``AutoBattleAgentContext.check_agent_related``,避免对
  ``last_screenshot``(None)的实际识别调用。
- 直接构造 ``TeamInfo`` + ``AgentInfo(AgentEnum.X.value)`` 设置队伍,控制 ``agent_list``。
- 调 ``append_agent_type_priority`` 后断言 dynamic_priority_list / dynamic_abandon_list。

核心分支:
- 队伍空(agent_list=[])→ 不修改 dynamic_priority_list(但会把所有非 UNKNOWN 类型加入
  dynamic_abandon_list,因为没有任何类型在 present_agent_type_set 中)。
- 队伍有某类型(如强攻)代理人 + 当前优先级无该类型 → 加入 dynamic_priority_list。
- 已在优先级 → 不重复加。
- 不在队伍的类型 → 加入 dynamic_abandon_list(除非被 specific priority rule 保护)。
"""
from unittest.mock import patch

from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)
from zzz_od.auto_battle.auto_battle_agent_context import AgentInfo, TeamInfo
from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum


def _setup_op(test_context: TestContext) -> LostVoidRunLevel:
    """构造 LostVoidRunLevel 实例并重置 lost_void 上下文 dynamic 列表。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    # 清空 challenge_config 中可能残留的 specific 优先级规则,避免影响 abandon 判定
    test_context.lost_void.challenge_config.artifact_priority = []
    test_context.lost_void.challenge_config.artifact_priority_2 = []
    test_context.lost_void.challenge_config.clear_artifact_priority_in_battle()
    test_context.lost_void.dynamic_priority_list = []
    test_context.lost_void.dynamic_abandon_list = []
    return LostVoidRunLevel(test_context, LostVoidRegionType.ENTRY)


def _set_team(test_context: TestContext, agents: list[AgentEnum]) -> None:
    """把战斗上下文的 team_info.agent_list 设置为指定的代理人列表。"""
    team_info = TeamInfo()
    team_info.agent_list = [AgentInfo(a.value) for a in agents]
    test_context.auto_battle_context.agent_context.team_info = team_info


def _run_append(op: LostVoidRunLevel) -> None:
    """调用 append_agent_type_priority,patch 掉对 screenshot 的实际识别。"""
    agent_context = op.ctx.auto_battle_context.agent_context
    with patch.object(agent_context, 'check_agent_related'):
        op.append_agent_type_priority()


def test_empty_team_no_modification(test_context: TestContext) -> None:
    """队伍空 → 提前返回,不修改 dynamic_priority_list / dynamic_abandon_list。"""
    op = _setup_op(test_context)
    _set_team(test_context, [])
    _run_append(op)
    # source: agent_list 为空时直接 round_success('非战斗区域'),两个 list 都不动
    assert test_context.lost_void.dynamic_priority_list == []
    assert test_context.lost_void.dynamic_abandon_list == []


def test_attack_agent_added_to_priority(test_context: TestContext) -> None:
    """队伍含强攻代理人(ELLEN)且优先级无强攻 → 加入 dynamic_priority_list。"""
    op = _setup_op(test_context)
    _set_team(test_context, [AgentEnum.ELLEN])  # ELLEN.agent_type == ATTACK(强攻)
    _run_append(op)
    assert test_context.lost_void.dynamic_priority_list == ['强攻']
    # 强攻在 present 集合中 → 从 abandon 移除;其余非 UNKNOWN 类型均进入 abandon
    expected_abandon = [t.value for t in AgentTypeEnum
                        if t != AgentTypeEnum.UNKNOWN and t != AgentTypeEnum.ATTACK]
    assert test_context.lost_void.dynamic_abandon_list == expected_abandon


def test_priority_already_has_type_not_duplicated(test_context: TestContext) -> None:
    """dynamic_priority_list 已含「强攻」→ 不重复追加。"""
    op = _setup_op(test_context)
    test_context.lost_void.dynamic_priority_list = ['强攻']
    _set_team(test_context, [AgentEnum.ELLEN])
    _run_append(op)
    assert test_context.lost_void.dynamic_priority_list == ['强攻']


def test_multiple_agent_types_in_team(test_context: TestContext) -> None:
    """队伍含多种类型(强攻 + 异常)→ 均加入 dynamic_priority_list;abandon 排除这两种。"""
    op = _setup_op(test_context)
    # ELLEN=ATTACK(强攻), GRACE=ANOMALY(异常)
    _set_team(test_context, [AgentEnum.ELLEN, AgentEnum.GRACE])
    _run_append(op)
    assert test_context.lost_void.dynamic_priority_list == ['强攻', '异常']
    expected_abandon = [t.value for t in AgentTypeEnum
                        if t not in (AgentTypeEnum.UNKNOWN, AgentTypeEnum.ATTACK,
                                     AgentTypeEnum.ANOMALY)]
    assert test_context.lost_void.dynamic_abandon_list == expected_abandon


def test_specific_priority_rule_protects_abandon(test_context: TestContext) -> None:
    """specific 优先级规则(如「异常 某藏品」)保护「异常」不被加入 abandon。"""
    op = _setup_op(test_context)
    # artifact_priority_2 含 specific 规则「异常 某某藏品」→ category「异常」受保护
    test_context.lost_void.challenge_config.artifact_priority_2 = ['异常 某某藏品']
    test_context.lost_void.challenge_config.clear_artifact_priority_in_battle()
    _set_team(test_context, [AgentEnum.ELLEN])  # 只在强攻,异常不在队伍
    _run_append(op)
    assert '异常' not in test_context.lost_void.dynamic_abandon_list, \
        'specific 规则「异常 某某藏品」应保护「异常」不被加入 abandon'


def test_pure_category_rule_does_not_protect(test_context: TestContext) -> None:
    """纯分类规则(如「异常」,无具体名)不视为 specific,不保护 abandon。"""
    op = _setup_op(test_context)
    test_context.lost_void.challenge_config.artifact_priority_2 = ['异常']
    test_context.lost_void.challenge_config.clear_artifact_priority_in_battle()
    _set_team(test_context, [AgentEnum.ELLEN])
    _run_append(op)
    assert '异常' in test_context.lost_void.dynamic_abandon_list, \
        '纯分类规则「异常」不应保护 abandon'


def test_present_type_removed_from_abandon(test_context: TestContext) -> None:
    """队伍中的类型即便预置在 abandon 中,也会被移除。"""
    op = _setup_op(test_context)
    # 预置 abandon 中含「强攻」
    test_context.lost_void.dynamic_abandon_list = ['强攻', '击破']
    _set_team(test_context, [AgentEnum.ELLEN])  # 强攻在队伍
    _run_append(op)
    assert '强攻' not in test_context.lost_void.dynamic_abandon_list, \
        '队伍中的类型应从 abandon 中移除'
    assert '强攻' in test_context.lost_void.dynamic_priority_list
