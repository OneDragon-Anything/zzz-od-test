from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.fixture_controller import WatchdogOperationMixin

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_store_carried import BagelStoreCarried

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.fixture_controller import FixtureController


class WatchedEnter(WatchdogOperationMixin, BagelEnter):
    """真实节点执行，观察恢复是否先于启动仓库。"""

    watchdog_max_rounds: int = 25


@pytest.mark.parametrize(
    'state',
    [
        '高危空局失败-原生1080',
        '主动退出-原生1080',
    ],
)
def test_recovery_reaches_warehouse_before_entry(
    test_context: TestContext, controller: FixtureController, state: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """恢复结算或退出提示后先转存启动仓库，不能直接进入选图。"""
    screen = '贝果-退出确认' if state == '主动退出-原生1080' else '贝果-结算'
    phases = [{'frame': (screen, state), 'exit': ('on_click_in', screen, '确认' if screen == '贝果-退出确认' else '继续')}]
    if screen == '贝果-退出确认':
        phases.append({'frame': ('贝果-结算', '高危空局失败-原生1080'), 'exit': ('on_click_in', '贝果-结算', '继续')})
    phases.append({'frame': ('贝果-仓库', '空局仓库-原生1080')})
    monkeypatch.setattr(BagelStoreCarried, 'execute', lambda _: OperationResult(False, '测试已到启动转存'))
    controller.set_phases(phases)
    op = WatchedEnter(test_context, allow_clear_loadout=True)
    with running_operation(op):
        result = op.execute()
    assert not result.success and '测试已到启动转存' in result.status
    assert controller.phase_idx == len(phases) - 1
