from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_reroll import BagelReroll
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord

if TYPE_CHECKING:
    from test.conftest import TestContext


class WatchedReroll(WatchdogOperationMixin, BagelReroll):
    """循环接错边时及时终止测试。"""

    watchdog_max_rounds: int = 30


@pytest.fixture
def setup_run(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> tuple[FixtureController, list[str], list[str]]:
    """复用已独立测过的子操作，只替换入退场，出生判断使用真实截图。"""
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    controller = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    scenes = ['雅努斯出生-r02-32s', '雅努斯出生-r01-39s']
    events: list[str] = []

    def enter(op: BagelEnter) -> OperationResult:
        """每次入场切换至下一张出生图，不伪造 A 判断结果。"""
        events.append('enter')
        controller.set_phases([{'frame': ('贝果-局内', scenes.pop(0))}])
        return OperationResult(True)

    def exit_run(op: BagelExit) -> OperationResult:
        """记录退出；实际退出交互由既有流程测试覆盖。"""
        events.append('exit')
        return OperationResult(True)

    def return_run(op: BagelReturn) -> OperationResult:
        """记录返回，以验证下一次入场前确实经过返回节点。"""
        events.append('return')
        return OperationResult(True)

    monkeypatch.setattr(BagelEnter, 'execute', enter)
    monkeypatch.setattr(BagelExit, 'execute', exit_run)
    monkeypatch.setattr(BagelReturn, 'execute', return_run)
    return controller, scenes, events


def execute(op: BagelReroll) -> OperationResult:
    """执行真实节点图并清理测试运行态。"""
    enter_running_state(op.ctx)
    try:
        return op.execute()
    finally:
        reset_running_state(op.ctx, op)


def test_non_a_restarts_then_a_stops(
    test_context: TestContext, setup_run: tuple,
) -> None:
    """非 A 完整返回再开，A 没有退出边，不发送移动或拾取输入。"""
    controller, _, events = setup_run
    op = WatchedReroll(test_context)
    result = execute(op)
    assert result.success and result.status == BagelReroll.STATUS_FOUND
    assert result.data['attempts'] == 2
    assert Path(result.data['screenshot']).is_file()
    assert events == ['enter', 'exit', 'return', 'enter']
    assert controller.recorded_inputs == []
    assert controller.recorded_clicks == []


@pytest.mark.parametrize('start,expected', [
    ('spawn', []), ('warehouse', ['return', 'enter']), ('entry', ['enter']),
])
def test_a_at_first_check_stops(
    test_context: TestContext, setup_run: tuple, start: str, expected: list[str],
) -> None:
    """三种起点均可命中 A，且不会在命中后多退一局。"""
    _, scenes, events = setup_run
    scenes[:] = ['雅努斯出生-r01-39s']
    result = execute(WatchedReroll(test_context, start=start))
    assert result.success and result.status == BagelReroll.STATUS_FOUND
    assert events == expected


def test_limit_returns_before_stopping(test_context: TestContext, setup_run: tuple) -> None:
    """最后一次非 A 先退出回入口，不超过上限再入场。"""
    _, _, events = setup_run
    result = execute(WatchedReroll(test_context, max_attempts=1))
    assert not result.success and '达到尝试上限' in result.status
    assert events == ['enter', 'exit', 'return']


@pytest.mark.parametrize('operation,expected', [
    (BagelEnter, []), (BagelExit, ['enter']), (BagelReturn, ['enter', 'exit']),
])
def test_child_failure_stops_without_restarting(
    test_context: TestContext, setup_run: tuple, monkeypatch: pytest.MonkeyPatch,
    operation: type, expected: list[str],
) -> None:
    """任一子操作失败直接保留现场，不将失败当成普通非 A 重开。"""
    _, _, events = setup_run
    child = MagicMock(return_value=OperationResult(False, '实测失败'))
    monkeypatch.setattr(operation, 'execute', child)
    result = execute(WatchedReroll(test_context))
    assert not result.success and result.status == '实测失败'
    assert events == expected
    child.assert_called_once()


def test_unknown_screen_does_not_exit(test_context: TestContext, setup_run: tuple) -> None:
    """加载或错误画面不能按非 A 处理并盲发退出。"""
    _, scenes, events = setup_run
    scenes[:] = ['加载-原生1080']
    result = execute(WatchedReroll(test_context))
    assert not result.success and '未识别贝果局内画面' in result.status
    assert events == ['enter']


def test_pending_items_do_not_block_entry(
    test_context: TestContext, setup_run: tuple, record: BagelRunRecord,
) -> None:
    """旧局未核对状态不阻止抽点，仍经入场操作后识别出生点。"""
    _, scenes, events = setup_run
    scenes[:] = ['雅努斯出生-r01-39s']
    before = Path(record.file_path).read_bytes()
    result = execute(WatchedReroll(test_context))
    assert result.success and result.status == BagelReroll.STATUS_FOUND
    assert events == ['enter']
    assert Path(record.file_path).read_bytes() == before


def test_manual_stop_prevents_next_entry(
    test_context: TestContext, setup_run: tuple, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """在返回过程中手动停止，即使子操作报告成功也不能再次入场。"""
    _, _, events = setup_run

    def stop(op: BagelReturn) -> OperationResult:
        """模拟停止快捷键改变框架状态。"""
        test_context.run_context.stop_running()
        return OperationResult(True)

    monkeypatch.setattr(BagelReturn, 'execute', stop)
    result = execute(WatchedReroll(test_context))
    assert not result.success and result.status == '人工结束'
    assert events == ['enter', 'exit']
