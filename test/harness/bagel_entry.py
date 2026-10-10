from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
)
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_return import BagelReturn

if TYPE_CHECKING:
    from test.conftest import TestContext


class BagelFixtureController(FixtureController):
    """只有剧本指定的交互键才推进，其他输入不能跳过画面。"""

    def btn_press(self, key: str, press_time: float | None = None) -> None:
        """记录按键并匹配当前画面需要的输入。"""
        self.recorded_inputs.append(key)
        if self._phases[self.phase_idx].get('key') == key:
            self._advance_phase()

    def interact(
        self,
        press: bool = False,
        press_time: float | None = None,
        release: bool = False,
    ) -> None:
        """达塔交互按 F 推进。"""
        self.btn_press('f', press_time)


class WatchedEnter(WatchdogOperationMixin, BagelEnter):
    """限制测试等待轮数，防止识别回归挂住。"""

    watchdog_max_rounds: int = 45


class WatchedExit(WatchdogOperationMixin, BagelExit):
    """限制测试等待轮数，防止识别回归挂住。"""

    watchdog_max_rounds: int = 30


class WatchedOpenBox(WatchdogOperationMixin, BagelOpenBox):
    """限制开箱搜查等待轮数。"""

    watchdog_max_rounds: int = 20


class WatchedReturn(WatchdogOperationMixin, BagelReturn):
    """限制返回流程轮数，避免画面剧本回归后无限等待。"""

    watchdog_max_rounds: int = 25


@pytest.fixture
def controller(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    no_round_wait: None,
) -> BagelFixtureController:
    """使用真截图、OCR 和区域，只替换输入及等待。"""
    result = BagelFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', result)
    return result
