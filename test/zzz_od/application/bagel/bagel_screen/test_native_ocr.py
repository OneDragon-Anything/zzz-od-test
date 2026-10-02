from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import pytest

from zzz_od.application.bagel.bagel_screen import (
    entry_warning,
    read_area,
    read_loadout,
    zero_loadout,
)

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('state,expected', [
    ('高危零装备价值', '零装备价值'),
    ('未装备武备', '未装备武备'),
    ('未穿戴队伍装备', '未穿戴队伍装备'),
])
def test_entry_warning_native(test_context: TestContext, state: str, expected: str) -> None:
    """原生截图必须识别完整提示，不能只凭确认按钮点击。"""
    screen = test_context.load_screen('贝果-入场确认', f'{state}-原生1080')
    text = read_area(test_context, screen, '贝果-入场确认', '提示')
    assert entry_warning(text) == expected, text


@pytest.mark.parametrize('state,expected', [
    ('高危零携带-原生1080', True),
    ('高危零携带-道具零误读O-20260929', True),
    ('零携带-原生1080', True),
    ('城郊高危零携带-20260926', True),
    ('仍带装备道具-1440缩放', False),
])
def test_zero_loadout_real_screen(test_context: TestContext, state: str, expected: bool) -> None:
    """实拍零携带与未清空物资应分别通过和拒绝。"""
    screen = test_context.load_screen('贝果-备战', state)
    values = read_loadout(test_context, screen)
    assert zero_loadout(values) is expected, values
    assert values['武备价值'] == '0'
    assert values['装备价值'] == ('0' if expected else '60000')
    assert values['道具价值'] == ('0' if expected else '38000')


@pytest.mark.parametrize('area_name', ['武备价值', '装备价值', '道具价值'])
@pytest.mark.parametrize('amount', ['1000', '1000000'])
def test_synthetic_nonzero_loadout_not_zero(
    test_context: TestContext, area_name: str, amount: str,
) -> None:
    """完整标题条中的多位金额必须保留高位，不能只读出末尾零。"""
    screen = test_context.load_screen('贝果-备战', '高危零携带-原生1080').copy()
    area = test_context.screen_loader.get_area('贝果-备战', area_name)
    rect = area.pc_rect
    left = rect.x2 - 175
    cv2.rectangle(screen, (left, rect.y1 + 2), (rect.x2 - 2, rect.y2 - 2), (140, 140, 140), -1)
    cv2.putText(
        screen, amount, (left + 5, rect.y2 - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA,
    )
    values = read_loadout(test_context, screen)
    assert values[area_name] == amount, values
    assert not zero_loadout(values)


def test_zero_investment_real_screen(test_context: TestContext) -> None:
    """实拍高危投资页的金额区域必须完整且只读出 0。"""
    screen = test_context.load_screen('贝果-入场确认', '高危零投资-原生1080')
    assert read_area(test_context, screen, '贝果-入场确认', '投资金额') == '0'


@pytest.mark.parametrize('amount, x', [('500000', 825), ('1000000', 800)])
def test_synthetic_nonzero_investment_not_zero(
    test_context: TestContext, amount: str, x: int,
) -> None:
    """在实拍页合成不同宽度白色金额，防止截断非零数字误认为零。"""
    screen = test_context.load_screen('贝果-入场确认', '高危零投资-原生1080').copy()
    cv2.rectangle(screen, (780, 700), (1139, 753), (28, 28, 28), -1)
    cv2.putText(screen, amount, (x, 740), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
    text = read_area(test_context, screen, '贝果-入场确认', '投资金额')
    assert text == amount
