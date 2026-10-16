"""正式任务从完整执行入口累计重试，不按连续失败数提前停止。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_storage import (
    WatchedApp,
)
from test.harness.bagel_storage import (
    app_setup as app_setup,
)
from test.harness.fixture_controller import enter_running_state, reset_running_state

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEnum,
)
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_operation import (
    BagelOperation,
    BagelRecoverableFailure,
)
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext

    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.application.bagel.bagel_run_record import BagelRunRecord

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.mark.parametrize(
    'budget',
    [
        0,
        1,
    ],
)
def test_retry_budget_from_formal_execute(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    budget: int,
) -> None:
    """混合原因共用累计额度，先结算最后一局再停，最大额度不被旧三次规则截断。"""
    config, record, events = app_setup
    config.max_failure_retries = budget
    controller = test_context.controller
    monkeypatch.setattr(controller, 'active_window', MagicMock(), raising=False)
    app = WatchedApp(test_context, config, record)
    app.watchdog_max_rounds = 1000
    monkeypatch.setattr(app, 'save_screenshot', lambda: '失败现场.webp')
    monkeypatch.setattr(
        app,
        'round_by_find_area',
        lambda screen, page, area: (
            app.round_success() if page == '战斗画面' else app.round_fail()
        ),
    )
    reasons = [
        '持续前进但位置未变化，停止移动',
        '小地图定位失败，停止移动',
        BagelOperation.STATUS_DEFEATED,
        BagelOperation.STATUS_TIMEOUT,
        BagelOperation.STATUS_INTERRUPTED,
    ]

    def navigate(op: BagelNavigate) -> OperationResult:
        """只替代游戏结果，正式应用和局内执行器仍走真实节点链。"""
        if events.count('enter') == 2:
            before = (app.failure_retries_used, app.initial_clear_pending)
            test_context.run_context._run_state = ApplicationRunContextStateEnum.PAUSE
            app._on_pause()
            test_context.run_context._run_state = ApplicationRunContextStateEnum.RUNNING
            app._on_resume()
            assert (
                (app.failure_retries_used, app.initial_clear_pending)
                == before
                == (1, False)
            )
        reason = reasons[(events.count('enter') - 1) % len(reasons)]
        data = (
            BagelRecoverableFailure(reason)
            if reason == reasons[0] or reason == reasons[1]
            else None
        )
        return OperationResult(False, reason, data)

    monkeypatch.setattr(BagelNavigate, 'execute', navigate)
    enter_running_state(test_context)
    try:
        result = app.execute()
        assert not result.success and f'整体重试已用 {budget}/{budget}' in result.status
        assert events == ['enter', 'exit', 'settle', 'return'] * budget + [
            'enter',
            'exit',
            'settle',
        ]
        assert app.failure_retries_used == budget
        assert app.defeat_rounds == budget + 1
        assert app.success_rounds == 0
        summary = record.get('retry_summary')
        assert summary['used'] == budget and summary['limit'] == budget
        assert len(summary['failures']) == budget + 1
        assert summary['stop_reason'] == result.status
    finally:
        reset_running_state(test_context, app)


@pytest.mark.parametrize(
    'kind',
    [
        'program',
        'stop',
    ],
)
def test_terminal_failure_does_not_restart(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    """实际框架异常和停止、子操作初始化失败及额外入场失败都不重开。"""
    config, record, events = app_setup
    app = WatchedApp(test_context, config, record)
    app.watchdog_max_rounds = 80
    if kind == 'program':

        def broken_build(op: BagelRunFlow, step: object) -> None:
            """从真实节点抛异常，不能伪装成普通超时。"""
            raise RuntimeError('程序故障')

        monkeypatch.setattr(BagelRunFlow, 'build_operation', broken_build)
    elif kind == 'initialization':

        def broken_init(op: BagelRunFlow) -> None:
            """使用真实 execute 的初始化失败出口。"""
            raise ValueError('资源损坏')

        monkeypatch.setattr(BagelRunFlow, 'handle_init', broken_init)
    elif kind == 'stop':

        def stop_build(op: BagelRunFlow, step: object) -> None:
            """节点中停止任务，后续框架循环直接结束。"""
            reset_running_state(test_context, op)

        monkeypatch.setattr(BagelRunFlow, 'build_operation', stop_build)
    else:

        def entry(op: BagelEnter) -> OperationResult:
            """额外入场失败，不获得下一次入场或返还额度。"""
            events.append('enter')
            return OperationResult(events.count('enter') == 1, '入场失败')

        monkeypatch.setattr(BagelEnter, 'execute', entry)
        monkeypatch.setattr(
            BagelNavigate,
            'execute',
            lambda op: OperationResult(False, op.STATUS_TIMEOUT),
        )
    enter_running_state(test_context)
    try:
        result = app.execute()
        assert not result.success
        assert events.count('enter') == (2 if kind == 'entry' else 1)
        assert app.failure_retries_used == (1 if kind == 'entry' else 0)
        if kind != 'entry':
            assert 'settle' not in events and 'return' not in events
        if kind == 'program':
            assert result.status == '异常' and '程序故障' in result.data
        elif kind == 'initialization':
            assert result.status == '初始化失败'
        elif kind == 'stop':
            assert result.status == '人工结束'
    finally:
        reset_running_state(test_context, app)


@pytest.mark.parametrize(
    'already_warehouse',
    [
        False,
    ],
)
def test_exhausted_retry_runs_real_exit_and_deposit(
    test_context: TestContext,
    app_setup: tuple[BagelConfig, BagelRunRecord, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    already_warehouse: bool,
) -> None:
    """正式任务从失败现场执行真实退出、核验入仓，额度为零时最终停在仓库。"""
    config, record, events = app_setup
    config.max_failure_retries = 0
    config.auto_clean_warehouse = False
    controller = test_context.controller
    monkeypatch.setattr(BagelExit, 'execute', BagelOperation.execute)
    monkeypatch.setattr(BagelSettleWarehouse, 'execute', BagelOperation.execute)

    def navigate(op: BagelNavigate) -> OperationResult:
        """失败已到仓库或死亡结算，两种新画面都可完成相同入仓核验。"""
        script = (
            []
            if already_warehouse
            else [
                {
                    'frame': ('贝果-结算', '高危空局失败-原生1080'),
                    'exit': ('on_click_in', '贝果-结算', '继续'),
                },
            ]
        )
        script.extend(
            [
                {
                    'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
                    'exit': ('on_click_in', '贝果-仓库', '放入仓库'),
                },
                {'frame': ('贝果-仓库', '入仓后安全箱空-r07-118s')},
            ]
        )
        controller.set_phases(script)
        return OperationResult(
            False, op.STATUS_TIMEOUT if already_warehouse else op.STATUS_DEFEATED
        )

    monkeypatch.setattr(BagelNavigate, 'execute', navigate)
    release = MagicMock()
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_app.release_flow_inputs', release
    )
    app = WatchedApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = app.execute()
        assert not result.success and '已完成仓库结算' in result.status
        assert events == ['enter']
        assert controller.phase_idx == len(controller._phases) - 1
        assert controller.click_hit_area('贝果-仓库', '放入仓库')
        assert len(controller.recorded_clicks) == (1 if already_warehouse else 2)
        assert app.success_rounds == 0 and app.defeat_rounds == 1
        assert app.failure_retries_used == 0
        assert release.call_count >= 2
    finally:
        reset_running_state(test_context, app)
