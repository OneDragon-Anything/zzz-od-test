"""局内步骤入口的定位暂缺等待、恢复与有界停止。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow

if TYPE_CHECKING:
    from test.conftest import TestContext

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.fixture
def location_op(monkeypatch: pytest.MonkeyPatch) -> BagelRunFlow:
    """保留真实定位器与步骤检查，只隔离 HUD 识别和游戏输入。"""
    ctx = MagicMock()
    ctx.screen_loader.get_area.return_value.pc_rect = Rect(1533, 206, 1734, 407)
    op = BagelRunFlow(ctx, load_published_flow('janus_high_b'), ('spawn',))
    op.vision = BagelRouteVision('janus_high_b')
    op.last_screenshot = cv2_utils.read_image(
        'zzz-od-test/screens/贝果-局内/白鸽出生定位短暂失配-20261002.webp',
    )
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_has', lambda area, screen_name='贝果-局内': area == '按键-普通攻击')
    return op


def test_persistent_real_location_gap_stops(
    location_op: BagelRunFlow, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持续几何证据不足在第五次等待后停止，不构建任何业务动作。"""
    op = location_op
    build = MagicMock()
    monkeypatch.setattr(op, 'build_operation', build)
    for _ in range(5):
        assert op.run_step().result == OperationRoundResultEnum.WAIT
    result = op.run_step()
    assert result.is_fail
    assert result.status == '小地图持续无法定位，停止并保留现场'
    assert op.cursor == 0
    build.assert_not_called()
    assert op.ctx.controller.mock_calls == []


def test_execute_location_gap_takes_fresh_frame(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """完整框架用原截图从失配流转到恢复，WAIT 后重新截图且不发送输入。"""
    controller = FixtureController(test_context)
    controller.set_phases([
        {'frame': ('贝果-局内', '白鸽出生定位短暂失配-20261002'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '白鸽出生定位恢复-20261002')},
    ])
    monkeypatch.setattr(test_context, 'controller', controller)
    cleanup = MagicMock()
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.release_flow_inputs', cleanup)
    events: list[dict[str, object]] = []
    op = BagelRunFlow(
        test_context, load_published_flow('janus_high_b'), ('spawn',), events.append,
    )
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert any(event['kind'] == 'waiting' for event in events)
        assert len([event for event in events if event['kind'] == 'done']) == 1
        assert controller.phase_idx == 1
        assert controller.recorded_clicks == []
        assert controller.recorded_inputs == []
        cleanup.assert_called_once_with(test_context)
    finally:
        reset_running_state(test_context, op)
