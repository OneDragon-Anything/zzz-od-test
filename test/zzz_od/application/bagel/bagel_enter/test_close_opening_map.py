from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_opening_map_is_closed_before_hud(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开局大地图不能空等自动关闭，识别后应主动关闭。"""
    test_context.mock_screen('贝果-局内', '六昏街南站地图-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.investment_confirmed = True
    op.confirmed_warnings.update({'零装备价值', '未装备武备', '未穿戴队伍装备'})
    click = MagicMock(return_value=True)
    monkeypatch.setattr(test_context.controller, 'click', click)
    op.screenshot()
    result = op.confirm_entry()
    assert result.result == OperationRoundResultEnum.WAIT
    assert result.status == '关闭开局大地图'
    click.assert_called()


@pytest.mark.parametrize('attack_visible', [True, False])
@pytest.mark.parametrize('investment_confirmed', [True, False])
def test_entry_uses_attack_button_after_investment(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    attack_visible: bool, investment_confirmed: bool,
) -> None:
    """左侧文字被遮挡仍可确认加载；攻击按钮缺失或未核验投资不能放行。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.investment_confirmed = investment_confirmed
    op.screenshot()
    op.last_screenshot = op.last_screenshot.copy()
    op.last_screenshot[160:250, 60:500] = 0
    if not attack_visible:
        rect = test_context.screen_loader.get_area('战斗画面', '按键-普通攻击').rect
        op.last_screenshot[rect.y1:rect.y2, rect.x1:rect.x2] = 0
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    result = op.confirm_entry()
    if attack_visible and investment_confirmed:
        assert result.is_success
        assert result.status == '已进入雅努斯高危'
    elif attack_visible:
        assert result.is_fail
        assert result.status == '未核对高危零投资，停止并保留现场'
    else:
        assert result.result == OperationRoundResultEnum.WAIT
    click.assert_not_called()
