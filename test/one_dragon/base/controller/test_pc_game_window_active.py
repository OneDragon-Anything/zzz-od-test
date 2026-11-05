"""PcGameWindow.active() 的激活结果复核。

窗口激活是否真的拿到前台焦点，不能只看 activate() 有没有抛异常：
前台锁、系统弹窗都会让调用正常返回但窗口没上来。这里用假窗口对象覆盖三种情况：
- 一次激活就聚焦；
- 第一次没聚焦、最小化再恢复后成功；
- 始终没聚焦，或者抛出 win32ui.error。
"""

import win32ui

from one_dragon.base.controller.pc_game_window import PcGameWindow


class _FakeWin:
    """最小化的窗口替身，只实现 active() 用到的方法和属性。"""

    def __init__(
            self,
            focus_on_activate: bool = True,
            raise_times: int = 0,
            error: BaseException | None = None,
    ):
        self.isActive: bool = False
        self.focus_on_activate: bool = focus_on_activate
        self.raise_times: int = raise_times
        self.error: BaseException | None = error
        self.activate_calls: int = 0
        self.minimize_calls: int = 0

    def restore(self) -> None:
        pass

    def activate(self) -> None:
        self.activate_calls += 1
        if self.raise_times > 0:
            self.raise_times -= 1
            if self.error is not None:
                raise self.error
            raise RuntimeError('activate failed')
        if self.focus_on_activate:
            self.isActive = True

    def minimize(self) -> None:
        self.minimize_calls += 1
        self.isActive = False


def _window_with(fake: _FakeWin) -> PcGameWindow:
    win = PcGameWindow()
    win._win = fake
    win._hWnd = 1
    return win


class TestPcGameWindowActive:

    def test_already_active_returns_true_without_activating(self):
        fake = _FakeWin(focus_on_activate=False)
        fake.isActive = True

        assert _window_with(fake).active() is True
        assert fake.activate_calls == 0

    def test_focused_after_activate_returns_true(self):
        fake = _FakeWin(focus_on_activate=True)

        assert _window_with(fake).active() is True
        assert fake.isActive is True
        assert fake.minimize_calls == 0

    def test_falls_back_to_minimize_when_first_activate_not_focused(self):
        fake = _FakeWin(focus_on_activate=False)

        assert _window_with(fake).active() is False
        assert fake.activate_calls == 2, '第一次没聚焦后要再试一次'
        assert fake.minimize_calls == 1, '重试前要先最小化'

    def test_generic_exception_falls_back_and_can_succeed(self):
        # 第一次抛异常，最小化恢复后再激活能聚焦
        fake = _FakeWin(focus_on_activate=True, raise_times=1, error=RuntimeError('boom'))

        assert _window_with(fake).active() is True
        assert fake.minimize_calls == 1

    def test_win32ui_error_returns_false_without_fallback(self):
        fake = _FakeWin(focus_on_activate=True, raise_times=1, error=win32ui.error('bad handle'))

        assert _window_with(fake).active() is False
        assert fake.minimize_calls == 0
