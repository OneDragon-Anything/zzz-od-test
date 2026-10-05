"""首次导航定位失配的松键等待、真实截图恢复与有界停止。"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_map_locator import MapLocation
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_route import BagelRoute
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow

if TYPE_CHECKING:
    from test.conftest import TestContext

pytestmark = pytest.mark.usefixtures('no_round_wait')
MISSING: str = '白鸽导航首次定位失配-20261002'
RECOVERED: str = '白鸽导航首次定位恢复-20261002'
WAIT_STATUS: str = '起步小地图暂时无法定位，等待下一帧'
INPUT_METHODS: tuple[str, ...] = (
    'start_moving_forward', 'move_w', 'move_a', 'move_s', 'move_d',
    'turn_by_angle_diff', 'interact',
)


def make_navigation(
    ctx: TestContext, monkeypatch: pytest.MonkeyPatch,
    map_id: str = 'janus_high_b', action: str = 'approach',
) -> BagelNavigate:
    """从正式发布步骤创建导航，只隔离 HUD 检查与实际输入。"""
    for name in (*INPUT_METHODS, 'stop_moving_forward'):
        monkeypatch.setattr(ctx.controller, name, MagicMock(), raising=False)
    flow = load_published_flow(map_id)
    step = next(step for step in flow.steps if step.action == action)
    op = BagelRunFlow(ctx, flow).build_operation(step)
    assert isinstance(op, BagelNavigate)
    op.handle_init()
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area == '按键-普通攻击' else op.round_fail()
    ))
    ctx.mock_screen('贝果-局内', RECOVERED)
    op.screenshot()
    return op


def no_motion(op: BagelNavigate) -> None:
    """允许松键，不允许移动、转向或交互。"""
    for name in INPUT_METHODS:
        getattr(op.ctx.controller, name).assert_not_called()


@pytest.fixture
def navigation(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> BagelNavigate:
    """使用白鸽同局真实恢复帧和正式定位器。"""
    return make_navigation(test_context, monkeypatch)


def test_real_initial_gap_recovers_only_on_fresh_position(navigation: BagelNavigate) -> None:
    """起点通过后的原失败帧最多等五次，恢复帧才开始导航。"""
    op = navigation
    assert op.check_start().status == '开始移动'
    assert op.last_position is None
    op.ctx.mock_screen('贝果-局内', MISSING)
    op.screenshot()
    for _ in range(5):
        result = op.move_to_target()
        assert result.result == OperationRoundResultEnum.WAIT
        assert result.status == WAIT_STATUS
        assert op.last_position is None
        assert op.steps == 0 and op.waypoint_index == 0
        no_motion(op)
    op.ctx.controller.stop_moving_forward.assert_called()
    op.ctx.mock_screen('贝果-局内', RECOVERED)
    op.screenshot()
    result = op.move_to_target()
    assert not result.is_fail, result.status
    assert op.last_position == pytest.approx((99.710, 99.821), abs=0.01)
    assert op.initial_locate_misses == 0


def test_persistent_real_initial_gap_fails_on_sixth_observation(navigation: BagelNavigate) -> None:
    """持续失配保持原停止状态，不能无限等待或发送探路输入。"""
    op = navigation
    op.ctx.mock_screen('贝果-局内', MISSING)
    op.screenshot()
    for _ in range(5):
        assert op.move_to_target().result == OperationRoundResultEnum.WAIT
    result = op.move_to_target()
    assert result.is_fail and result.status == '小地图定位失败，停止移动'
    assert op.last_position is None
    no_motion(op)


@pytest.mark.parametrize(('map_id', 'action'), [
    ('janus_high_a', 'move'), ('janus_high_a', 'approach'), ('janus_high_b', 'approach'),
])
@pytest.mark.parametrize('reason', [
    'insufficient_geometry', 'ambiguous_position', 'outside_coverage', 'invalid_crop',
])
def test_only_initial_insufficient_geometry_waits(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    map_id: str, action: str, reason: str,
) -> None:
    """移动和靠近只等待几何暂缺，危险定位不被拾取物旁路掩盖。"""
    op = make_navigation(test_context, monkeypatch, map_id, action)
    monkeypatch.setattr(op.vision, 'locate', lambda _crop: None)
    op.vision.last_location = MapLocation(None, 'test-map', reason, '', 0, None, 0)
    monkeypatch.setattr(op, '_ignoring_pickup', lambda: True)
    op.heading_aligned = True
    wait = MagicMock()
    monkeypatch.setattr(op, '_after_round_wait', wait)
    result = op.move_to_target()
    if reason == 'insufficient_geometry':
        assert result.result == OperationRoundResultEnum.WAIT
        assert result.status == WAIT_STATUS
        wait.assert_called_with(wait=0.3, wait_round_time=None)
        assert sum(call.kwargs.get('wait') is not None for call in wait.call_args_list) == 1
    else:
        expected = (
            f'小地图定位失败：{reason}' if action == 'approach'
            else '小地图定位失败，停止移动'
        )
        assert result.is_fail and result.status == expected
    assert op.last_position is None
    no_motion(op)
    op.ctx.controller.stop_moving_forward.assert_called()


def test_restart_resets_initial_wait_budget(navigation: BagelNavigate) -> None:
    """操作再次初始化时，等待次数不能沿用旧执行。"""
    op = navigation
    op.ctx.mock_screen('贝果-局内', MISSING)
    op.screenshot()
    for _ in range(5):
        assert op.move_to_target().result == OperationRoundResultEnum.WAIT
    op.handle_init()
    assert op.initial_locate_misses == 0
    assert op.move_to_target().result == OperationRoundResultEnum.WAIT
    assert op.initial_locate_misses == 1
    no_motion(op)


def test_existing_in_motion_miss_budget_is_unchanged(navigation: BagelNavigate) -> None:
    """取得位置后仍最多等三次，每次 0.15 秒，不借用起步预算。"""
    op = navigation
    op.ctx.mock_screen('贝果-局内', MISSING)
    op.screenshot()
    op.last_position = (99.710, 99.821)
    for _ in range(3):
        result = op.move_to_target()
        assert result.result == OperationRoundResultEnum.WAIT
        assert result.status == '小地图暂时对不上，再看一帧'
    assert op.move_to_target().is_fail
    assert op.initial_locate_misses == 0
    no_motion(op)


class WatchedInitialNavigate(WatchdogOperationMixin, BagelNavigate):
    """完整框架的等待必须在有限轮内推进或停止。"""

    watchdog_max_rounds: int = 15


@pytest.mark.parametrize('recovers', [True, False])
def test_execute_initial_gap_takes_new_screenshots(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, recovers: bool,
) -> None:
    """用真实截图走完整节点链，确认 WAIT 换帧且无探路动作。"""
    controller = FixtureController(test_context)
    phases = [
        {'frame': ('贝果-局内', RECOVERED), 'exit': ('on_polls', 1)},
        {'frame': ('贝果-局内', MISSING), 'exit': ('on_polls', 2)},
    ] if recovers else [
        {'frame': ('贝果-局内', RECOVERED), 'exit': ('on_polls', 1)},
        {'frame': ('贝果-局内', MISSING)},
    ]
    if recovers:
        phases.append({'frame': ('贝果-局内', RECOVERED)})
    controller.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', controller)
    for name in (*INPUT_METHODS, 'stop_moving_forward'):
        monkeypatch.setattr(controller, name, MagicMock(), raising=False)
    step = next(step for step in load_published_flow('janus_high_b').steps if step.action == 'approach')
    point = replace(step.waypoints[0], xy=(100, 100))
    op = WatchedInitialNavigate(
        test_context, map_id='janus_high_b', require_spawn=False, coordinate_only=True,
        route_data=BagelRoute('janus_high_b', (point,)),
    )
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area == '按键-普通攻击' else op.round_fail()
    ))
    observations: list[dict[str, object]] = []
    op.on_observation = observations.append
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success == recovers, result.status
        assert any(item['position'] is None for item in observations)
        if recovers:
            assert result.status == op.STATUS_WAYPOINT
            assert observations[-1]['position'] is not None
            assert controller.phase_idx == 2
        else:
            assert result.status == '小地图定位失败，停止移动'
            assert len(observations) == 6
        no_motion(op)
    finally:
        reset_running_state(test_context, op)
