from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
)
from zzz_od.application.bagel.bagel_clean import FILTER_TICKS, BagelCleanWarehouse
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext


class WatchedClean(WatchdogOperationMixin, BagelCleanWarehouse):
    """限制清理轮数。"""

    watchdog_max_rounds: int = 40


class WatchedSettle(WatchdogOperationMixin, BagelSettleWarehouse):
    """限制结算编排轮数。"""

    watchdog_max_rounds: int = 20


@pytest.fixture
def controller(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """真截图与 OCR，点击按剧本推进。"""
    result = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', result)
    return result


def _clean_phases(sell_area: str) -> list[dict]:
    """从仓库主界面走到快速选择，再按 0 件或有件分流。"""
    phases: list[dict] = [
        {
            'frame': ('贝果-仓库', '空局仓库-原生1080'),
            'exit': ('on_click_in', '贝果-仓库', '批量出售'),
        },
        {
            'frame': ('贝果-仓库', '仓库批量出售中'),
            'exit': ('on_click_in', '贝果-仓库', '批量选择'),
        },
    ]
    for index, name in enumerate(FILTER_TICKS):
        phases.append(
            {
                'frame': ('贝果-仓库', f'快速选择-步骤{index}-20260921'),
                'exit': ('on_click_in', '贝果-仓库', name),
            }
        )
    phases.append(
        {
            'frame': ('贝果-仓库', '快速选择-步骤7-20260921'),
            'exit': ('on_click_in', '贝果-仓库', '筛选确认'),
        }
    )
    phases.append(
        {
            'frame': ('贝果-仓库', '仓库批量出售中'),
            'exit': ('on_click_in', '贝果-仓库', sell_area),
        }
    )
    if sell_area == '确认出售':
        phases.append(
            {
                'frame': ('贝果-仓库', '出售二次确认-20260921'),
                'exit': ('on_click_in', '贝果-仓库', '出售弹窗确认'),
            }
        )
        phases.append(
            {
                'frame': ('贝果-仓库', '出售获得硬币-20260921'),
                'exit': ('on_click_in', '贝果-仓库', '出售获得确认'),
            }
        )
    phases.append({'frame': ('贝果-仓库', '空局仓库-原生1080')})
    return phases


def _patch_settle_ops(
    monkeypatch: pytest.MonkeyPatch,
    deposit_statuses: list[str],
    clean_status: str = BagelCleanWarehouse.STATUS_DONE,
) -> list[str]:
    """按预定状态替换入仓和清理，记录调用顺序。"""
    events: list[str] = []
    deposits = list(deposit_statuses)

    def deposit_exec(self: BagelDeposit) -> OperationResult:
        events.append('deposit')
        status = deposits.pop(0)
        success = status != '入仓失败'
        return OperationResult(
            success,
            status,
            {'safe_count': 2} if status == BagelDeposit.STATUS_FULL else None,
        )

    def clean_exec(self: BagelCleanWarehouse) -> OperationResult:
        events.append('clean')
        return OperationResult(True, clean_status)

    monkeypatch.setattr(BagelDeposit, 'execute', deposit_exec)
    monkeypatch.setattr(BagelCleanWarehouse, 'execute', clean_exec)
    return events
