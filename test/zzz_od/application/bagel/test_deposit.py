from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_storage import BagelDragController as BagelDragController
from test.harness.bagel_storage import WatchedDeposit as WatchedDeposit
from test.harness.bagel_storage import _clicks_in_area as _clicks_in_area
from test.harness.bagel_storage import controller as controller
from test.harness.fixture_controller import (
    enter_running_state,
    reset_running_state,
)

from zzz_od.application.bagel.bagel_deposit import BagelDeposit

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize(
    'after,success',
    [
        (259, True),
        (258, False),
        (None, False),
    ],
)
def test_deposit_stacked_items_and_invalid_counts(
    test_context: TestContext,
    controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch,
    after: int | None,
    success: bool,
) -> None:
    """模拟合并堆叠后格数不变；下降或读数缺失仍拒绝，截图保留真实清空过程。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
                'exit': ('on_click_in', '贝果-仓库', '放入仓库'),
            },
            {'frame': ('贝果-仓库', '入仓后安全箱空-r07-118s')},
        ]
    )
    op = WatchedDeposit(test_context)
    counts = iter([259, after])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success is success, result.status
        assert controller.click_hit_area('贝果-仓库', '放入仓库')
        if success:
            assert result.status == BagelDeposit.STATUS_DONE
            assert result.data['warehouse_after'] == result.data['warehouse_before']
            assert result.data['moved'] == 5  # 入仓前的安全箱格数，不是物品件数。
    finally:
        reset_running_state(test_context, op)


def test_deposit_full_when_safe_stays_and_capacity_used_up(
    test_context: TestContext,
    controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """安全箱仍占用且全部格子已满时，记仓满成功而不是入仓成功。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
                'exit': ('on_click_in', '贝果-仓库', '放入仓库'),
            },
            {'frame': ('贝果-仓库', '带物资仓库-r07-117s')},
        ]
    )
    op = WatchedDeposit(test_context)
    monkeypatch.setattr(op, '_warehouse_pair', lambda: (280, 280))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelDeposit.STATUS_FULL
        assert result.data['safe_count'] == 5
        assert controller.click_hit_area('贝果-仓库', '放入仓库')
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize(
    'used',
    [
        279,
    ],
    ids=['has_space'],
)
def test_partial_deposit_stops_without_second_click(
    test_context: TestContext,
    controller: BagelDragController,
    monkeypatch: pytest.MonkeyPatch,
    used: int,
) -> None:
    """满仓或未满仓都不能接受部分入仓，也不能再点一次。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
                'exit': ('on_click_in', '贝果-仓库', '放入仓库'),
            },
            {'frame': ('贝果-仓库', '带物资仓库-r07-117s')},
        ]
    )
    op = WatchedDeposit(test_context)
    monkeypatch.setattr(op, '_warehouse_pair', lambda: (used, 280))
    counts = iter([5, 4])
    monkeypatch.setattr(op, '_safe_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '部分入仓' in result.status
        assert _clicks_in_area(test_context, controller, '放入仓库') == 1
    finally:
        reset_running_state(test_context, op)
