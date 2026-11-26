from __future__ import annotations

import gc
import time
import weakref
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import numpy as np
import pytest

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEventEnum,
)
from one_dragon.base.operation.context_event_bus import ContextEventBus, ContextEventItem
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class ScreenshotOperation(Operation):
    def __init__(self, ctx: OneDragonContext, succeed: bool) -> None:
        super().__init__(ctx, need_check_game_win=False)
        self.succeed = succeed

    def handle_init(self) -> None:
        self.ctx.listen_event('test-operation-global-event', self._on_global_event)

    def _on_global_event(self, event: ContextEventItem) -> None:
        pass

    @operation_node(name='截图', is_start_node=True)
    def capture(self) -> OperationRoundResult:
        if self.succeed:
            return self.round_success()
        return self.round_fail('测试失败')


@pytest.mark.parametrize('succeed', [True, False])
def test_completed_operation_removes_listeners_and_releases_screenshot(
    monkeypatch: pytest.MonkeyPatch, succeed: bool,
) -> None:
    def screenshot() -> tuple[float, np.ndarray]:
        return time.time(), np.zeros((8, 8, 3), dtype=np.uint8)

    monkeypatch.setattr('one_dragon.base.operation.operation.send_node_notify', lambda *args: None)
    run_bus = ContextEventBus()
    global_bus = ContextEventBus()
    global_bus.run_context = SimpleNamespace(
        event_bus=run_bus, is_context_stop=False, is_context_pause=False,
    )
    global_bus.controller = SimpleNamespace(screenshot=screenshot)
    operation = ScreenshotOperation(cast('OneDragonContext', global_bus), succeed)

    assert operation.execute().success is succeed
    assert operation.last_screenshot is not None
    screenshot_ref = weakref.ref(operation.last_screenshot)
    operation_ref = weakref.ref(operation)
    del operation
    gc.collect()

    assert not global_bus.has_event_listener('test-operation-global-event')
    assert not run_bus.has_event_listener(ApplicationRunContextStateEventEnum.PAUSE)
    assert not run_bus.has_event_listener(ApplicationRunContextStateEventEnum.RESUME)
    assert operation_ref() is None
    assert screenshot_ref() is None
