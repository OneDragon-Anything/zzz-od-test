from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext


from test.harness.bagel_loadout import mock_loadout_ocr


@pytest.mark.parametrize(
    'missing_warehouse_areas',
    [
        False,
    ],
)
def test_unknown_screen_never_transports_or_clicks(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    missing_warehouse_areas: bool,
) -> None:
    """无法识别的画面不尝试通用返回或地图传送。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.screenshot()
    if missing_warehouse_areas:
        for name in ('材料道具', '音擎仓库', '驱动仓库'):
            monkeypatch.delitem(
                test_context.screen_loader._screen_area_map, f'仓库-{name}.标题-{name}'
            )
    monkeypatch.setattr(op, 'round_by_find_area', lambda *_args: op.round_retry())
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda *_args: None)
    transport = MagicMock()
    click = MagicMock()
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_enter.Transport.execute', transport
    )
    monkeypatch.setattr(test_context.controller, 'click', click)
    result = op.open_hub()
    assert result.is_fail
    transport.assert_not_called()
    click.assert_not_called()


def test_unrelated_confirmation_is_not_accepted(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
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


@pytest.mark.parametrize(
    'full_values,crop_values,area_index',
    [
        (['0', '@500'], None, 0),
        ([], ['0', '@500'], 1),
        (['0', '500'], ['0'], 2),
    ],
)
def test_conflicting_value_prevents_entry(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    area_index: int,
    full_values: list[str],
    crop_values: list[str] | None,
) -> None:
    """任一价值区存在非零证据时，面板或标题条裁剪读到零均不得点击入场。"""
    area, label = (
        ('武备价值', '代理人武备'),
        ('装备价值', '装备'),
        ('道具价值', '道具'),
    )[area_index]
    mock_loadout_ocr(
        test_context, monkeypatch, area, [label, *full_values], crop_values
    )
    op = BagelEnter(test_context)
    op.last_screenshot = test_context.load_screen('贝果-备战', '高危零携带-原生1080')
    monkeypatch.setattr(
        op, 'round_by_find_area', MagicMock(return_value=op.round_success())
    )
    click = MagicMock(return_value=op.round_success())
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)

    for _ in range(4):
        assert op.verify_zero_loadout().result == OperationRoundResultEnum.WAIT
        click.assert_not_called()
    assert op.verify_zero_loadout().is_fail
    assert not op.zero_checked
    click.assert_not_called()


def test_hud_without_investment_check_stops(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
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
