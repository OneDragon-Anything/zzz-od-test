from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_full_four_slot_safe_never_drags_into_locked_slot(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """用四格实拍合成满箱和同品质结果，不能向第五个锁格拖拽。"""
    screen = test_context.load_screen('贝果-局内', '四格安全箱部分占用-20261004').copy()
    source = SAFE_SLOT_CENTERS[0]
    patch = screen[source.y - 58:source.y + 55, source.x - 49:source.x + 49].copy()
    for center in (*SAFE_SLOT_CENTERS[1:4], RESULT_SLOT_CENTERS[0]):
        screen[center.y - 58:center.y + 55, center.x - 49:center.x + 49] = patch
    op = BagelStoreSafe(test_context)
    op.last_screenshot = screen
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op, '_search_complete', lambda: True)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    result = op.store_next()
    assert result.is_success and result.status == op.STATUS_DONE
    drag.assert_not_called()


@pytest.mark.parametrize('has_results', [False, True])
def test_unknown_safe_stops_without_dragging(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, has_results: bool,
) -> None:
    """有无搜查结果都不能把未知安全箱报告成正常完成。"""
    screen = test_context.load_screen('贝果-局内', '四格安全箱部分占用-20261004').copy()
    if has_results:
        source, dest = SAFE_SLOT_CENTERS[0], RESULT_SLOT_CENTERS[0]
        screen[dest.y - 40:dest.y + 40, dest.x - 40:dest.x + 40] = screen[
            source.y - 40:source.y + 40, source.x - 40:source.x + 40,
        ]
    screen[851:947, 312:408] = 0
    op = BagelStoreSafe(test_context)
    op.last_screenshot = screen
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op, '_search_complete', lambda: True)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    result = op.store_next()
    assert result.is_fail and '状态不明' in result.status
    drag.assert_not_called()
