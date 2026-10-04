from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_loadout import (
    WatchedClear,
    running_operation,
)
from test.harness.bagel_loadout import controller as controller

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_clear_loadout import (
    LOADOUT_CENTERS,
)

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


@pytest.mark.parametrize('interruption', ['pause', 'first_failed', 'second_failed'])
def test_double_click_interruption_stops(
    test_context: TestContext, controller: TransferController,
    monkeypatch: pytest.MonkeyPatch, interruption: str,
) -> None:
    """点击失败或两次点击间暂停时停止，不续点详情菜单。"""
    source = LOADOUT_CENTERS[-1]
    op = WatchedClear(test_context)
    calls: list[Point] = []

    def click(pos: Point, press_time: float = 0) -> bool:
        calls.append(pos)
        if interruption == 'pause':
            op.handle_pause()
            op.handle_resume()
        return not ((interruption == 'first_failed' and len(calls) == 1)
                    or (interruption == 'second_failed' and len(calls) == 2))

    monkeypatch.setattr(controller, 'click', click)
    with running_operation(op):
        assert op.double_click_item(source, '道具第 4 格').is_fail
        assert len(calls) == (2 if interruption == 'second_failed' else 1)
        assert op.moved == 0


def test_pause_during_pre_click_wait_sends_no_input(
    test_context: TestContext, controller: TransferController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """点击前等待期间暂停又恢复，旧截图选中的物品不得继续点击。"""
    op = WatchedClear(test_context)
    click = MagicMock(return_value=True)
    monkeypatch.setattr(controller, 'click', click)

    def pause_and_resume(_: float) -> None:
        op.handle_pause()
        op.handle_resume()

    monkeypatch.setattr('zzz_od.application.bagel.bagel_transfer.time.sleep', pause_and_resume)
    with running_operation(op):
        result = op.double_click_item(LOADOUT_CENTERS[-1], '道具第 4 格')
        assert result.result.name == 'WAIT'
        click.assert_not_called()
        assert not op.pending
        assert op.moved == 0
