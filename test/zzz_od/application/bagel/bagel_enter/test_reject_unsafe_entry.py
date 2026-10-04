from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_loadout import mock_loadout_ocr

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('checked,repeat,expected', [
    (False, False, '尚未核对零携带'),
    (True, True, '入场确认未消失'),
])
def test_confirmation_guard(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    checked: bool, repeat: bool, expected: str,
) -> None:
    """未核验及已经点过的弹窗都不再次输入。"""
    test_context.mock_screen('贝果-入场确认', '高危零装备价值-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = checked
    if repeat:
        op.confirmed_warnings.add('零装备价值')
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    op.screenshot()
    result = op.confirm_entry()
    assert expected in result.status
    assert result.result == (OperationRoundResultEnum.RETRY if repeat else OperationRoundResultEnum.FAIL)
    click.assert_not_called()


def test_unrelated_confirmation_is_not_accepted(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """退出确认与入场确认按钮重叠，必须拒绝完整提示不符的弹窗。"""
    test_context.mock_screen('贝果-退出确认', '主动退出-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = True
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    op.screenshot()
    result = op.confirm_entry()
    assert result.is_fail
    assert result.status == '未知入场确认，停止并保留现场'
    click.assert_not_called()


def test_carried_equipment_prevents_entry(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有队伍装备和道具时停在备战，不能消费任何出战确认。"""
    test_context.mock_screen('贝果-备战', '仍带装备道具-1440缩放')
    op = BagelEnter(test_context)
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    op.screenshot()
    assert op.verify_zero_loadout().is_fail
    assert not op.zero_checked
    click.assert_not_called()


@pytest.mark.parametrize('area_index', [0, 1, 2])
@pytest.mark.parametrize('full_values,crop_values', [
    (['0', '@500'], None),
    ([], ['0', '@500']),
    (['0', '500'], ['0']),
])
def test_conflicting_value_prevents_entry(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    area_index: int, full_values: list[str], crop_values: list[str] | None,
) -> None:
    """任一价值区存在非零证据时，面板或标题条裁剪读到零均不得点击入场。"""
    area, label = (('武备价值', '代理人武备'), ('装备价值', '装备'), ('道具价值', '道具'))[area_index]
    mock_loadout_ocr(test_context, monkeypatch, area, [label, *full_values], crop_values)
    op = BagelEnter(test_context)
    op.last_screenshot = test_context.load_screen('贝果-备战', '高危零携带-原生1080')
    monkeypatch.setattr(op, 'round_by_find_area', MagicMock(return_value=op.round_success()))
    click = MagicMock(return_value=op.round_success())
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)

    for _ in range(4):
        assert op.verify_zero_loadout().result == OperationRoundResultEnum.WAIT
        click.assert_not_called()
    assert op.verify_zero_loadout().is_fail
    assert not op.zero_checked
    click.assert_not_called()


def test_repeat_investment_page_does_not_click(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已确认过零投资却仍在原页时等待，而不重复点击。"""
    test_context.mock_screen('贝果-入场确认', '高危零投资-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.investment_confirmed = True
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.read_area', lambda *_: '0')
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    op.screenshot()
    result = op.confirm_entry()
    assert result.result == OperationRoundResultEnum.RETRY
    assert result.status == '零投资入场未生效'
    click.assert_not_called()


def test_hud_without_investment_check_stops(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """即使已见贝果 HUD，未经零投资核验也不得报告成功。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.confirmed_warnings.update({'零装备价值', '未装备武备', '未穿戴队伍装备'})
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    op.screenshot()
    result = op.confirm_entry()
    assert result.is_fail
    assert result.status == '未核对高危零投资，停止并保留现场'
    click.assert_not_called()
