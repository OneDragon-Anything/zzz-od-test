from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_SWAP,
    BagelSlotMark,
    StoreChoice,
)
from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


pytestmark = pytest.mark.usefixtures('no_round_wait')


def test_visible_item_is_moved_before_search_finishes(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """搜查中已显露的物品可提前拖入安全箱，但未结束时不关闭面板。"""
    op = BagelStoreSafe(test_context)
    test_context.mock_screen('贝果-局内', '武备箱待入箱-实机')
    op.screenshot()
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op._panel_guard, 'observe', lambda *_: True)
    monkeypatch.setattr(op, '_search_complete', lambda: False)
    monkeypatch.setattr(op, '_stable_results', lambda results: results)
    mark = BagelSlotMark(0, RESULT_SLOT_CENTERS[0], 'S', '贵重物品')
    choice = StoreChoice('fill', 0, 0, mark)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_occupied', lambda *_args: [mark])
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.choose_store_action', lambda *_args: choice)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    assert op.store_next().status == '已拖拽一件'
    drag.assert_called_once_with(RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[0])


def test_no_further_choice_waits_until_search_complete(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """箱满或仅有货币时，搜索中仍等待后续物品；完成后才收尾。"""
    op = BagelStoreSafe(test_context)
    test_context.mock_screen('贝果-局内', '武备箱待入箱-实机')
    op.screenshot()
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op._panel_guard, 'observe', lambda *_: True)
    monkeypatch.setattr(op, '_search_complete', lambda: False)
    monkeypatch.setattr(op, '_stable_results', lambda results: results)
    mark = BagelSlotMark(0, RESULT_SLOT_CENTERS[0], 'A', '其他')
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_occupied', lambda *_args: [mark])
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.choose_store_action', lambda *_args: None)
    assert op.store_next().result == OperationRoundResultEnum.WAIT
    monkeypatch.setattr(op, '_search_complete', lambda: True)
    assert op.store_next().status == BagelStoreSafe.STATUS_DONE


def test_search_status_ocr_gap_fails_after_limit(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """面板还在但状态持续无法识别时有界停止。"""
    test_context.mock_screen('贝果-局内', '武备箱搜查中-r07')
    op = BagelStoreSafe(test_context)
    op.screenshot()
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    original_find = op.round_by_find_area

    def find_area(screen: object, screen_name: str, area_name: str):
        if area_name in {'搜查完成', '搜查进行中'}:
            return op.round_fail('OCR 暂时漏识别')
        return original_find(screen, screen_name, area_name)

    monkeypatch.setattr(op, 'round_by_find_area', find_area)
    for _ in range(5):
        assert op.store_next().result == OperationRoundResultEnum.WAIT
    assert op.store_next().result == OperationRoundResultEnum.FAIL


def test_does_not_swap_while_search_is_running(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """搜索动画未结束时不根据变化中的安全箱角标执行对换。"""
    op = BagelStoreSafe(test_context)
    test_context.mock_screen('贝果-局内', '武备箱搜查中-r07')
    op.screenshot()
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_search_ready', lambda: True)
    monkeypatch.setattr(op._panel_guard, 'observe', lambda *_: True)
    monkeypatch.setattr(op, '_search_complete', lambda: False)
    monkeypatch.setattr(op, '_stable_results', lambda results: results)
    mark = BagelSlotMark(4, RESULT_SLOT_CENTERS[4], 'S', '其他')
    choice = StoreChoice(ACTION_SWAP, 4, 3, mark)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.inspect_occupied', lambda *_args: [mark])
    monkeypatch.setattr('zzz_od.application.bagel.bagel_store.choose_store_action', lambda *_args: choice)
    drag = MagicMock()
    monkeypatch.setattr(op, '_drag_item', drag)
    assert op.store_next().result == OperationRoundResultEnum.WAIT
    drag.assert_not_called()
    monkeypatch.setattr(op, '_search_complete', lambda: True)
    assert op.store_next().status == '已拖拽一件'
    drag.assert_called_once()
