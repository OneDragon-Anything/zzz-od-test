"""describe_operation 透传 docstring 描述测试。"""
from test.conftest import TestContext

from zzz_od.backend import operation_registry


def test_describe_operation_includes_description(test_context: TestContext) -> None:
    """describe_operation 返回含 description(优先 class docstring,回退 __init__ docstring)。"""
    # RestartInBattle 无 class docstring,但 __init__ 有「在战斗画面 尝试退出」→ 回退取到
    result = operation_registry.describe_operation(
        test_context, 'zzz_od.operation.challenge_mission.restart_in_battle.RestartInBattle',
    )
    assert 'description' in result
    assert '退出' in result['description']
