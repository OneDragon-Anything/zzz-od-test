"""KeyboardMouseController 松键/按压门禁的单元测试。

用 ``__new__`` 注入 fake keyboard/mouse，不创建真实 pynput Controller；
按键名映射用真实的 ``pc_button_utils``。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from pynput import keyboard, mouse

from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button import keyboard_mouse_controller as controller_module
from one_dragon.base.controller.pc_button.keyboard_mouse_controller import KeyboardMouseController


class _FakeKeyboard:
    """只记录 press/release/tap 调用。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    def press(self, key: Any) -> None:
        self.events.append(('press', key))

    def release(self, key: Any) -> None:
        self.events.append(('release', key))

    def tap(self, key: Any) -> None:
        self.events.append(('tap', key))


class _FakeMouse:
    """只记录 press/release/click 调用。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    def press(self, button: Any) -> None:
        self.events.append(('press', button))

    def release(self, button: Any) -> None:
        self.events.append(('release', button))

    def click(self, button: Any) -> None:
        self.events.append(('click', button))


def _make_controller() -> KeyboardMouseController:
    controller = KeyboardMouseController.__new__(KeyboardMouseController)
    controller.keyboard = _FakeKeyboard()
    controller.mouse = _FakeMouse()
    controller._pressed_keys = set()
    controller._pressed_lock = threading.Lock()
    return controller


@contextmanager
def _capture_logs() -> Iterator[list[logging.LogRecord]]:
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler()
    logger = controller_module.log
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


def _messages(records: list[logging.LogRecord], level: int) -> list[str]:
    return [r.getMessage() for r in records if r.levelno == level]


def test_release_sends_key_up_even_with_empty_ledger() -> None:
    """账本为空也要发 key-up：账本只记状态，不再当门禁。"""
    controller = _make_controller()

    controller.release('a')

    assert controller.keyboard.events == [('release', keyboard.KeyCode.from_char('a'))]
    assert controller.mouse.events == []
    assert controller._pressed_keys == set()


@pytest.mark.parametrize('bad_key', ['invalid', ''])
def test_release_invalid_key_logs_error_and_sends_nothing(bad_key: str) -> None:
    """无效键名不抛异常、只记 ERROR，不发 key-up。"""
    controller = _make_controller()
    with _capture_logs() as records:
        controller.release(bad_key)

    assert controller.keyboard.events == []
    assert controller.mouse.events == []
    assert any('无效的按键名' in message for message in _messages(records, logging.ERROR))


def test_release_mouse_left_uses_mouse_branch() -> None:
    """鼠标键释放走 mouse.release，不碰 keyboard。"""
    controller = _make_controller()

    controller.release('mouse_left')

    assert controller.mouse.events == [('release', mouse.Button.left)]
    assert controller.keyboard.events == []


def test_press_invalid_key_not_recorded_and_not_sent() -> None:
    """无效键名 press 不入账本、不发 press。"""
    controller = _make_controller()
    with _capture_logs() as records:
        controller.press('invalid')

    assert controller.keyboard.events == []
    assert controller.mouse.events == []
    assert controller._pressed_keys == set()
    assert any('无效的按键名' in message for message in _messages(records, logging.ERROR))


def test_reset_continues_after_one_key_fails() -> None:
    """reset 中一个键 release 抛异常，其余键仍被释放、不向上抛。"""
    controller = _make_controller()
    controller._pressed_keys = {'a', 'b', 'c'}
    original_release = controller.release

    def flaky_release(key: str) -> None:
        if key == 'b':
            raise RuntimeError('boom')
        original_release(key)

    controller.release = flaky_release  # type: ignore[method-assign]
    with _capture_logs() as records:
        controller.reset()  # 不应抛

    released = {key for action, key in controller.keyboard.events if action == 'release'}
    assert keyboard.KeyCode.from_char('a') in released
    assert keyboard.KeyCode.from_char('c') in released
    assert any('松开按键' in message for message in _messages(records, logging.ERROR))


def test_release_holds_ledger_lock_while_sending_key_up() -> None:
    """账本删除与 key-up 在同一把锁里：fake release 内断言锁已持有。"""
    controller = _make_controller()
    lock_states: list[bool] = []
    fake_keyboard = controller.keyboard

    def asserting_release(key: Any) -> None:
        lock_states.append(controller._pressed_lock.locked())
        fake_keyboard.events.append(('release', key))

    fake_keyboard.release = asserting_release  # type: ignore[method-assign]
    controller.release('a')

    assert lock_states == [True]
    assert controller.keyboard.events == [('release', keyboard.KeyCode.from_char('a'))]


@pytest.mark.parametrize(('key', 'unknown'), [
    ('a', False),
    ('space', False),
    ('numpad_1', False),
    ('numpad_a', True),
    ('', True),
    ('invalid', True),
])
def test_unknown_keyboard_key_matches_old_condition(key: str, unknown: bool) -> None:
    """helper 判断与旧 ``isinstance(get_keyboard_button(k), str)`` 等价。"""
    real_key = pc_button_utils.get_keyboard_button(key)
    assert KeyboardMouseController._is_unknown_keyboard_key(real_key) is unknown
    assert (isinstance(real_key, str)) is unknown
