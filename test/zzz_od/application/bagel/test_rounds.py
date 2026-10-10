from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_storage import BagelDragController as BagelDragController
from test.harness.bagel_storage import WatchedApp as WatchedApp
from test.harness.bagel_storage import app_setup as app_setup
from test.harness.bagel_storage import controller as controller
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_app_non_a_restarts_then_collects(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非 A 先退出返回，再入场命中 A 后走收集链。"""
    config, record, events = app_setup
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    scenes = ['雅努斯出生-r02-32s', '雅努斯出生-r01-39s']

    def enter(self: BagelEnter) -> OperationResult:
        events.append('enter')
        controller.set_phases([{'frame': ('贝果-局内', scenes.pop(0))}])
        return OperationResult(True)

    monkeypatch.setattr(BagelEnter, 'execute', enter)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r02-32s')}])
    op = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert events == [
            'enter',
            'exit',
            'return',
            'enter',
            'move',
            'navigate',
            'open',
            'store',
            'close',
            'move',
            'move',
            'move',
            'navigate_safe',
            'interact_safe',
            'unlock',
            'store',
            'close',
            'exit',
            'settle',
            'return',
        ]
        assert op.success_rounds == 1
    finally:
        reset_running_state(test_context, op)


def test_app_zero_limit_continues_after_success(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """填 0 时成功入仓两局后仍尝试进入下一局，不因成功次数结束。"""
    config, record, events = app_setup
    config.max_success_rounds = 0
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    op = WatchedApp(test_context, config, record)
    op.watchdog_max_rounds = 52
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert op.success_rounds >= 2
        assert events.count('enter') > 2
        assert events.count('return') >= 2
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize(
    'rounds,limit,success,expected_count',
    [
        (['defeat', 'defeat', 'success', 'defeat', 'defeat', 'success'], 2, True, 2),
        (['defeat', 'skip', 'defeat', 'empty', 'defeat'], 1, False, 0),
    ],
)
def test_app_success_and_skip_do_not_reset_failure_retries(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    rounds: list[str],
    limit: int,
    success: bool,
    expected_count: int,
) -> None:
    """成功、非支持出生点和空箱均不清零；失败有物入仓仍不计成功。"""
    config, record, events = app_setup
    config.max_success_rounds = limit
    config.max_failure_retries = 5 if success else 2
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    round_idx = -1
    original_navigate = BagelNavigate.execute

    def enter(self: BagelEnter) -> OperationResult:
        """按局切换真实出生截图，超出剧本就让测试失败。"""
        nonlocal round_idx
        round_idx += 1
        scene = (
            '雅努斯出生-r02-32s'
            if rounds[round_idx] == 'skip'
            else '雅努斯出生-r01-39s'
        )
        events.append('enter')
        controller.set_phases([{'frame': ('贝果-局内', scene)}])
        return OperationResult(True)

    def navigate(self: BagelNavigate) -> OperationResult:
        """只有指定局撤离失败，其余照常完成收集。"""
        if rounds[round_idx] in ('defeat', 'interrupted'):
            status = (
                BagelOperation.STATUS_DEFEATED
                if rounds[round_idx] == 'defeat'
                else BagelOperation.STATUS_INTERRUPTED
            )
            return OperationResult(False, status)
        return original_navigate(self)

    def settle(self: BagelSettleWarehouse) -> OperationResult:
        """失败局即使带回物资也不能计入成功局数。"""
        events.append('settle')
        status = (
            BagelDeposit.STATUS_EMPTY
            if rounds[round_idx] == 'empty'
            else BagelDeposit.STATUS_DONE
        )
        return OperationResult(True, status)

    monkeypatch.setattr(BagelEnter, 'execute', enter)
    monkeypatch.setattr(BagelNavigate, 'execute', navigate)
    monkeypatch.setattr(BagelSettleWarehouse, 'execute', settle)
    op = WatchedApp(test_context, config, record)
    op.watchdog_max_rounds = 130
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success is success, result.status
        assert events.count('enter') == len(rounds)
        assert events.count('settle') == len(rounds) - rounds.count('skip')
        assert events.count('return') == len(rounds) - (not success)
        assert op.success_rounds == expected_count
        assert op.defeat_rounds == rounds.count('defeat') + rounds.count('interrupted')
        assert op.failure_retries_used == op.defeat_rounds - (not success)
        if not success:
            assert '整体重试已用 2/2' in result.status
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize(
    'failed_stage',
    [
        BagelExit,
        BagelSettleWarehouse,
        BagelReturn,
    ],
)
def test_app_defeat_cleanup_error_stops_without_reentry(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    failed_stage: type[BagelOperation],
) -> None:
    """失败局退出、结算或返回出错时保留原始错误，不重开或伪报达到失败上限。"""
    config, record, events = app_setup
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    monkeypatch.setattr(
        BagelNavigate,
        'execute',
        lambda self: OperationResult(False, BagelOperation.STATUS_DEFEATED),
    )
    monkeypatch.setattr(
        failed_stage,
        'execute',
        lambda self: OperationResult(False, '收尾核验失败'),
    )
    op = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '收尾核验失败' in result.status
        assert BagelOperation.STATUS_DEFEATED in result.status
        assert events.count('enter') == 1
        assert op.success_rounds == 0
        if failed_stage in (BagelExit, BagelSettleWarehouse):
            assert 'return' not in events
        if failed_stage is BagelExit:
            assert 'settle' not in events
    finally:
        reset_running_state(test_context, op)
