from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_warehouse import WatchedClean as WatchedClean
from test.harness.bagel_warehouse import WatchedSettle as WatchedSettle
from test.harness.bagel_warehouse import _clean_phases as _clean_phases
from test.harness.bagel_warehouse import _patch_settle_ops as _patch_settle_ops
from test.harness.bagel_warehouse import controller as controller
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    reset_running_state,
)

from zzz_od.application.bagel.bagel_clean import FILTER_TICKS, BagelCleanWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_clean_zero_count_cancels_without_selling(
    test_context: TestContext,
    controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """筛选 0 件时确认筛选后取消出售，不能点确认出售。"""
    controller.set_phases(_clean_phases('取消出售'))
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_clean.parse_filter_count', lambda _text: 0
    )
    op = WatchedClean(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelCleanWarehouse.STATUS_SKIPPED
        for name in ('批量出售', '批量选择', '筛选确认', *FILTER_TICKS):
            assert controller.click_hit_area('贝果-仓库', name), name
        assert not controller.click_hit_area('贝果-仓库', '确认出售')
        last = controller.recorded_clicks[-1]
        cancel = test_context.screen_loader.get_area('贝果-仓库', '取消出售').pc_rect
        assert cancel.x1 <= last.x <= cancel.x2 and cancel.y1 <= last.y <= cancel.y2
    finally:
        reset_running_state(test_context, op)


def test_clean_positive_count_confirms_sell(
    test_context: TestContext,
    controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有待出售件数时点确认出售，不取消。"""
    controller.set_phases(_clean_phases('确认出售'))
    op = WatchedClean(test_context)
    counts = iter([280, 279])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelCleanWarehouse.STATUS_DONE
        assert controller.click_hit_area('贝果-仓库', '确认出售')
        last = controller.recorded_clicks[-1]
        assert controller.click_hit_area('贝果-仓库', '出售弹窗确认')
        confirm = test_context.screen_loader.get_area(
            '贝果-仓库', '出售获得确认'
        ).pc_rect
        assert confirm.x1 <= last.x <= confirm.x2 and confirm.y1 <= last.y <= confirm.y2
    finally:
        reset_running_state(test_context, op)


def test_clean_refuses_occupied_safe_from_real_frame(
    test_context: TestContext,
    controller: FixtureController,
) -> None:
    """仓满且安全箱仍有物资时，不进入批量出售。"""
    controller.set_phases([{'frame': ('贝果-仓库', '满仓安全箱余一件-20260924')}])
    op = WatchedClean(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '安全箱仍有物资' in result.status
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)
