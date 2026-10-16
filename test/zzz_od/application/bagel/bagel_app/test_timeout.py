"""真实框架节点和操作超时从正式入口进入失败结算。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_storage import WatchedApp
from test.harness.bagel_storage import (
    app_setup as app_setup,
)
from test.harness.fixture_controller import enter_running_state, reset_running_state

from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow

if TYPE_CHECKING:
    from test.conftest import TestContext

    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
    from zzz_od.context.zzz_context import ZContext

pytestmark = pytest.mark.usefixtures('no_round_wait')


class TimedStep(BagelOperation):
    """只替代游戏等待，超时由真实框架产生。"""

    def __init__(self, ctx: ZContext, operation_timeout: bool) -> None:
        """区分整个操作超时和单节点超时。"""
        super().__init__(ctx, timeout_seconds=0 if operation_timeout else -1)

    @operation_node(
        name='无已知失败文字的等待', is_start_node=True, timeout_seconds=0.001
    )
    def wait_unknown_reason(self) -> OperationRoundResult:
        """任意等待文字不能决定能否恢复。"""
        return self.round_wait('新步骤仍在等待', wait=1)


@pytest.mark.parametrize(
    'operation_timeout',
    [
        True,
    ],
)
def test_real_framework_timeout_reaches_formal_cleanup(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    operation_timeout: bool,
) -> None:
    """无分类文字的真实节点或操作超时仍先结算，零额度时不进入下一局。"""
    config, record, events = app_setup
    config.max_failure_retries = 0
    monkeypatch.setattr(
        BagelRunFlow,
        'build_operation',
        lambda op, step: TimedStep(test_context, operation_timeout),
    )
    app = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = app.execute()
        assert not result.success
        assert '执行超时' in result.status and '已完成仓库结算' in result.status
        assert events == ['enter', 'exit', 'settle']
        assert app.failure_retries_used == 0 and app.success_rounds == 0
    finally:
        reset_running_state(test_context, app)


def test_final_exit_timeout_stays_at_scene(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常收集后的退出已经失败，不能被当作普通局内超时再次退出或重开。"""
    from one_dragon.base.operation.operation_base import OperationResult
    from zzz_od.application.bagel.bagel_exit import BagelExit

    config, record, events = app_setup
    exits: list[str] = []

    def exit_failed(op: BagelExit) -> OperationResult:
        """实际退出只允许被调用一次。"""
        exits.append('exit')
        return OperationResult(False, op.STATUS_TIMEOUT)

    monkeypatch.setattr(BagelExit, 'execute', exit_failed)
    app = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = app.execute()
        assert (
            not result.success and result.status == BagelOperation.STATUS_CLEANUP_FAILED
        )
        assert '执行超时' in result.data
        assert exits == ['exit']
        assert events.count('enter') == 1
        assert 'settle' not in events and 'return' not in events
        assert app.failure_retries_used == 0
    finally:
        reset_running_state(test_context, app)
