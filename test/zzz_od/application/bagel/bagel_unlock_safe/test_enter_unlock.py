from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from test.conftest import TestContext

from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe


def test_enter_unlock_uses_attack_button(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """普通攻击按钮与保险箱交互提示共同确认可以交互。"""
    test_context.mock_screen('贝果-局内', '电子保险箱交互-HUD错字-20260930')
    op = BagelUnlockSafe(test_context)
    op.screenshot()
    assert op.round_by_find_area(op.last_screenshot, '战斗画面', '按键-普通攻击').is_success
    assert op.round_by_find_area(op.last_screenshot, '贝果-局内', '电子保险箱交互').is_success
    press = MagicMock()
    monkeypatch.setattr(test_context.controller, 'interact', press)

    result = op.enter_unlock()

    assert result.is_success, result.status
    assert result.status == '已按F进入解锁'
    press.assert_called_once_with(press=True, press_time=0.2, release=True)
    assert op.round_by_find_area(op.last_screenshot, '战斗画面', '按键-普通攻击').is_success


@pytest.mark.parametrize('missing_area', ['按键-普通攻击', '电子保险箱交互'])
def test_enter_unlock_requires_hud_and_interaction(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, missing_area: str,
) -> None:
    """分别遮去HUD或右侧交互提示，仍禁止发送F；不把箱子头顶名称当提示。"""
    test_context.mock_screen('贝果-局内', '电子保险箱交互-HUD错字-20260930')
    op = BagelUnlockSafe(test_context)
    op.screenshot()
    screen = op.last_screenshot.copy()
    screen_name = '战斗画面' if missing_area == '按键-普通攻击' else '贝果-局内'
    rect = test_context.screen_loader.get_area(screen_name, missing_area).rect
    screen[rect.y1:rect.y2, rect.x1:rect.x2] = 0
    test_context.add_mock_screenshot(screen)
    op.screenshot()
    press = MagicMock()
    monkeypatch.setattr(test_context.controller, 'interact', press)

    assert op.enter_unlock().is_fail
    press.assert_not_called()


@pytest.mark.parametrize('state, expected_status', [
    ('高危开局大地图-原生1080', '未发现电子保险箱交互提示'),
    ('电子保险箱搜索完成', BagelUnlockSafe.STATUS_UNLOCKED),
    ('电子保险箱第1轮小圈', '已在解锁界面'),
])
def test_enter_unlock_does_not_press_on_other_screens(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    state: str, expected_status: str,
) -> None:
    """非局内画面、已经开始解锁或搜查时均不重复交互。"""
    test_context.mock_screen('贝果-局内', state)
    op = BagelUnlockSafe(test_context)
    op.screenshot()
    press = MagicMock()
    monkeypatch.setattr(test_context.controller, 'interact', press)

    assert op.enter_unlock().status == expected_status
    press.assert_not_called()
