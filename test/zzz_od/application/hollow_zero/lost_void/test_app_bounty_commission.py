"""LostVoidApp.check_bounty_commission_before 非悬赏模式分支测试。

按 testing methodology 动作一:``check_bounty_commission_before`` 在非悬赏模式下
(``extra_task != '完成悬赏委托'``),按 ``is_finished_by_day`` / ``mission_name`` 路由
到不同 status:
- ``is_finished_by_day=True`` → ``STATUS_ENOUGH_TIMES``('完成通关次数')
- ``mission_name == '矩阵行动'`` → ``STATUS_AGAIN_MATRIX``('继续挑战-矩阵行动')
- 其余 mission → ``STATUS_AGAIN``('继续挑战')

纯配置测试,无画面依赖:用 ``PropertyMock`` patch ``is_bounty_commission_mode`` /
``is_finished_by_day``,设置 ``mission_name`` 后调方法断言 status。

``LostVoidApp`` 实例化可行:仅需 ``test_context`` + ``lost_void_debug`` +
``next_region_type``,不触发 GUI/注册(详见 zzz_application.ZApplication.__init__)。
"""
from unittest.mock import PropertyMock, patch

import pytest
from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.lost_void_app import LostVoidApp
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)


def _setup_op(test_context: TestContext) -> LostVoidApp:
    """构造 LostVoidApp 实例(直接实例化,无需 mock)。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    return LostVoidApp(
        test_context,
        lost_void_debug=False,
        next_region_type=LostVoidRegionType.ENTRY,
    )


def _run_non_bounty(op: LostVoidApp, mission_name: str,
                    finished_by_day: bool) -> str:
    """在非悬赏模式下运行 check_bounty_commission_before,返回 status。

    用 PropertyMock patch:
    - ``LostVoidConfig.is_bounty_commission_mode`` → False
    - ``LostVoidRunRecord.is_finished_by_day`` → finished_by_day
    """
    op.config.mission_name = mission_name
    with patch.object(type(op.config), 'is_bounty_commission_mode',
                      new_callable=PropertyMock, return_value=False), \
         patch.object(type(op.run_record), 'is_finished_by_day',
                      new_callable=PropertyMock, return_value=finished_by_day):
        result = op.check_bounty_commission_before()
    return result.status


def test_finished_by_day_returns_enough_times(test_context: TestContext) -> None:
    """非悬赏 + is_finished_by_day=True → STATUS_ENOUGH_TIMES。"""
    op = _setup_op(test_context)
    status = _run_non_bounty(op, mission_name='战线肃清', finished_by_day=True)
    assert status == LostVoidApp.STATUS_ENOUGH_TIMES
    assert status == '完成通关次数'


def test_matrix_action_returns_again_matrix(test_context: TestContext) -> None:
    """非悬赏 + is_finished_by_day=False + 矩阵行动 → STATUS_AGAIN_MATRIX。"""
    op = _setup_op(test_context)
    status = _run_non_bounty(op, mission_name='矩阵行动', finished_by_day=False)
    assert status == LostVoidApp.STATUS_AGAIN_MATRIX
    assert status == '继续挑战-矩阵行动'


@pytest.mark.parametrize('mission_name', ['战线肃清', '特遣调查'])
def test_other_mission_returns_again(test_context: TestContext,
                                     mission_name: str) -> None:
    """非悬赏 + is_finished_by_day=False + 非矩阵行动 mission → STATUS_AGAIN。"""
    op = _setup_op(test_context)
    status = _run_non_bounty(op, mission_name=mission_name, finished_by_day=False)
    assert status == LostVoidApp.STATUS_AGAIN
    assert status == '继续挑战'


def test_finished_by_day_takes_precedence_over_mission(test_context: TestContext) -> None:
    """is_finished_by_day=True 优先于 mission_name 分支(即便 mission=矩阵行动)。"""
    op = _setup_op(test_context)
    status = _run_non_bounty(op, mission_name='矩阵行动', finished_by_day=True)
    assert status == LostVoidApp.STATUS_ENOUGH_TIMES


def test_app_instantiation_is_lightweight(test_context: TestContext) -> None:
    """LostVoidApp 实例化不需要 mock 重依赖,直接构造可用。"""
    op = _setup_op(test_context)
    assert op.config is not None
    assert op.run_record is not None
    assert op.priority_agent_list == []
    assert op.use_priority_agent is False
