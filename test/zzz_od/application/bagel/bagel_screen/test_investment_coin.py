from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import numpy as np
import pytest

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_investment import (
    mask_investment_coin,
    read_investment,
)
from zzz_od.application.bagel.bagel_screen import read_area

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('amount', ['0', '500K', '1M', '1.5M', '2M', '2.5M', '3M'])
def test_all_live_amounts_keep_complete_digits(test_context: TestContext, amount: str) -> None:
    """七档实机金额完整读取，不能因金币位置变化截断首位。"""
    screen = test_context.load_screen('贝果-入场确认', f'投资{amount}-20261007-无损')
    assert read_investment(test_context, screen) == amount


def test_coin_read_as_two_no_longer_clicks_min(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
) -> None:
    """原图确实把金币读成 2；实际入场节点应只确认零投资，不点 MIN。"""
    screen = test_context.load_screen('贝果-入场确认', '零投资金币误读2-20261007-无损')
    assert read_area(test_context, screen, '贝果-入场确认', '投资金额') == '20'
    assert read_investment(test_context, screen) == '0'
    op = BagelEnter(test_context)
    op.last_screenshot = screen
    op.zero_checked = True
    click = MagicMock(return_value=op.round_success())
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)
    assert op.confirm_entry().result == OperationRoundResultEnum.WAIT
    assert op.investment_confirmed
    assert click.call_args.args[2] == '零投资前往空洞'
    assert op.investment_retries == 0


@pytest.mark.parametrize('case', ['missing', 'multiple', 'digit_left'])
def test_unreliable_coin_location_stays_unknown(test_context: TestContext, case: str) -> None:
    """金币缺失、重复或位于数字右侧时不能通过遮挡得到假零。"""
    screen = test_context.load_screen('贝果-入场确认', '零投资金币误读2-20261007-无损').copy()
    crop = screen[700:754, 780:1140]
    coin = crop[:, 147:186].copy()
    if case == 'missing':
        crop[:, 147:186] = 0
    elif case == 'multiple':
        crop[:, 20:59] = coin
    else:
        crop[12:36, 10:18] = 255
    assert mask_investment_coin(crop) is None
    assert read_investment(test_context, screen) == ''


def test_mask_keeps_input_and_all_amount_pixels(test_context: TestContext) -> None:
    """遮挡只生成新图，保持尺寸，不改变金币右侧的完整金额。"""
    screen = test_context.load_screen('贝果-入场确认', '投资500K-20261007-无损')
    crop = screen[700:754, 780:1140]
    before = crop.copy()
    result = mask_investment_coin(crop)
    assert result is not None and result.shape == crop.shape
    assert np.array_equal(crop, before)
    assert np.array_equal(result[:, 151:], crop[:, 151:])
