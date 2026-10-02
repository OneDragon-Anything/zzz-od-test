from __future__ import annotations

from dataclasses import replace
from math import cos, radians, sin
from pathlib import Path
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
from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_map_locator import MapLocation
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow
from zzz_od.controller.zzz_pc_controller import ZPcController

if TYPE_CHECKING:
    from test.conftest import TestContext

    from one_dragon.base.operation.operation_round_result import OperationRoundResult


pytestmark = pytest.mark.usefixtures('no_round_wait')


def published_navigation(
    ctx: TestContext,
    action: str = 'move',
    target: str = 'box',
    role: str | None = None,
    map_id: str = 'janus_high_a',
) -> BagelNavigate:
    """按正式执行器创建一个发布步骤，不拼装旧版整段路线。"""
    flow = load_published_flow(map_id)
    if action == 'move':
        # 参数仅定位既有测试样本；普通移动本身已不再保存容器或路点角色。
        index = 1 if target == 'box' else {'entry': 6, 'turn': 7, 'approach': 8}[role or 'entry']
        step = flow.steps[index]
        assert step.target is None
    else:
        step = next(step for step in flow.steps if step.action == action and step.target == target)
    if action == 'move' and target == 'box':
        # 固定短步测试的目的地，避免正式路线微调后跨过持续移动的距离边界。
        step = replace(step, waypoints=(replace(
            step.waypoints[0], xy=(110, 100), tolerance=1, passed_tolerance=3,
        ),))
    navigation = BagelRunFlow(ctx, flow).build_operation(step)
    assert isinstance(navigation, BagelNavigate)
    assert not navigation.require_spawn and navigation.check_target_position
    navigation.handle_init()
    navigation.screenshot()
    navigation.heading_aligned = True
    return navigation


@pytest.fixture
def op(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> BagelNavigate:
    """正式巷口移动使用发布流程和 RGB 框架截图，输入全部记录。"""
    test_context.mock_screen('贝果-局内', '雅努斯出生-r01-39s')
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', MagicMock(), raising=False)
    monkeypatch.setattr(test_context.controller, 'start_moving_forward', MagicMock(), raising=False)
    monkeypatch.setattr(test_context.controller, 'turn_by_angle_diff', MagicMock(), raising=False)
    for key in 'wasd':
        monkeypatch.setattr(test_context.controller, f'move_{key}', MagicMock())
    return published_navigation(test_context)


def test_spawn_and_first_step_use_framework_rgb(op: BagelNavigate) -> None:
    """正式移动入口用 RGB 截图定位，角色箭头驱动第一步。"""
    assert op.check_start().status == '开始移动'
    result = op.move_to_target()
    assert result.status == '前往巷口左转'
    op.ctx.controller.move_w.assert_called_once_with(press=True, press_time=0.2, release=True)
    for key in 'asd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()


def test_non_a_never_moves(op: BagelNavigate, test_context: TestContext) -> None:
    """保留旧整段入口兼容：另一出生地连续偏离后跳过，不尝试探路。"""
    op = BagelNavigate(test_context)
    test_context.mock_screen('贝果-局内', '雅努斯出生-r02-32s')
    op.screenshot()
    result = op.check_start()
    for _ in range(5):
        if result.result != OperationRoundResultEnum.RETRY:
            break
        result = op.check_start()
    assert result.is_success and result.status == BagelNavigate.STATUS_UNSUPPORTED
    for key in 'wasd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()


def test_spawn_locate_miss_waits_then_starts(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧整段入口兼容：出生配准暂缺后恢复时开始走。"""
    op = BagelNavigate(op.ctx)
    op.screenshot()
    calls = {'count': 0}
    spawn = op.vision.spawn

    def locate(_crop: object) -> tuple[float, float] | None:
        calls['count'] += 1
        if calls['count'] == 1:
            return None
        return spawn

    monkeypatch.setattr(op.vision, 'locate', locate)
    missed = op.check_start()
    assert missed.result == OperationRoundResultEnum.RETRY
    assert missed.status == '小地图暂时对不上出生点'
    started = op.check_start()
    assert started.is_success and started.status == '开始移动'


def test_box_prompt_stops_before_moving(op: BagelNavigate, test_context: TestContext) -> None:
    """独立第七局箱前提示出现后，不能继续沿目标点过冲。"""
    test_context.mock_screen('贝果-局内', '雅努斯箱前-r07-32s')
    op = published_navigation(op.ctx, action='approach')
    assert op.move_to_target().status == BagelNavigate.STATUS_ARRIVED_BOX
    for key in 'wasd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()


def test_live_corner_continues_towards_box(
    op: BagelNavigate, test_context: TestContext,
) -> None:
    """真实失败帧经 RGB 裁图和定位后，应边走边转向箱子，而不是定位失败。"""
    root = next(path for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')
    test_context.add_mock_screenshot(cv2_utils.read_image(str(root / 'screens/贝果-局内/雅努斯转角定位失败-1440缩放.webp')))
    op = published_navigation(op.ctx, action='approach')
    result = op.move_to_target()
    assert result.status.startswith('行进转向')
    assert 0 < op.ctx.controller.turn_by_angle_diff.call_args.args[0] <= 30
    op.ctx.controller.start_moving_forward.assert_called_once()
    for key in 'wasd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()


@pytest.mark.parametrize('case,expected', [
    ('position', '小地图定位失败'),
    ('direction', '无法识别角色箭头'),
    ('limit', '导航达到动作上限'),
    ('missing_box', '已到轮胎旁武备箱前但未发现武备箱交互'),
])
def test_navigation_stops_on_missing_evidence(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch, case: str, expected: str,
) -> None:
    """定位丢失、方向不可读或到点无箱时直接停止，不尝试恢复。"""
    if case == 'position':
        monkeypatch.setattr(op.vision, 'locate', lambda _: None)
    elif case == 'direction':
        monkeypatch.setattr(op.vision, 'player_angle', lambda _: None)
    elif case == 'limit':
        op.steps = op._action_limit()
    else:
        op = published_navigation(op.ctx, action='approach')
        monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 84))
    result = op.move_to_target()
    if case == 'missing_box':
        assert result.status == '目标前停步等待交互提示'
        op.last_screenshot_time += 2
        result = op.move_to_target()
    assert result.is_fail and expected in result.status
    op.ctx.controller.stop_moving_forward.assert_called()
    for key in 'wasd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()


def test_reaching_corner_advances_then_turns_left(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正式巷口步骤完成后停步；下一靠近步骤独立转向北侧武备箱。"""
    monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    assert op.move_to_target().status == BagelNavigate.STATUS_WAYPOINT
    op.ctx.controller.stop_moving_forward.assert_called()
    op = published_navigation(op.ctx, action='approach')
    monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    assert op.move_to_target().status.startswith('停车转向')
    op.ctx.controller.turn_by_angle_diff.assert_called_once_with(90)
    for key in 'wasd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()


class NavigationController(FixtureController):
    """输入后切到下一帧实拍，核对节点之间重新截图的行为。"""

    def stop_moving_forward(self) -> None:
        """记录器不持有真实按键。"""

    def turn_by_angle_diff(self, angle_diff: float) -> None:
        """转向后切换到下一张图，不在原截图中校准。"""
        assert 0 < abs(angle_diff) <= 90
        self.recorded_inputs.append('turn')
        self._advance_phase()

    def move_w(
        self, press: bool = False, press_time: float | None = None, release: bool = False,
    ) -> None:
        """只记录短步和校准，不向游戏发送输入。"""
        assert press and release and press_time in (0.08, 0.2)
        self.recorded_inputs.append('w')
        self._advance_phase()

    def start_moving_forward(self) -> None:
        """按住前进并切到下一张图。"""
        self.recorded_inputs.append('hold')
        self._advance_phase()


class WatchedNavigate(WatchdogOperationMixin, BagelNavigate):
    """若未按预期到达终态，使测试及时失败。"""

    watchdog_max_rounds: int = 8


def test_navigation_rechecks_after_step(
    op: BagelNavigate, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """用真实首尾截图验证转向后重新观察并结束；不模拟真实移动距离。"""
    controller = NavigationController(test_context)
    controller.set_phases([
        {'frame': ('贝果-局内', '雅努斯出生-r01-39s')},
        {'frame': ('贝果-局内', '雅努斯箱前-r07-32s')},
    ])
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelNavigate', WatchedNavigate)
    navigation = published_navigation(test_context, action='approach')
    enter_running_state(test_context)
    try:
        result = navigation.execute()
        assert result.success and result.status == BagelNavigate.STATUS_ARRIVED_BOX, result.status
        assert controller.recorded_inputs == ['turn']
        assert controller.phase_idx == 1
    finally:
        reset_running_state(test_context, navigation)


def test_initial_probe_requires_new_frame(op: BagelNavigate) -> None:
    """第一步只校准，不能从同一张旧截图连续移动。"""
    op.heading_aligned = False
    assert op.move_to_target().status == '短按W后等待箭头对齐'
    op.ctx.controller.move_w.assert_called_once_with(press=True, press_time=0.08, release=True)
    assert op.move_to_target().status == '等待动作后的新截图'
    assert op.ctx.controller.move_w.call_count == 1
    op.last_screenshot_time += 1
    assert op.move_to_target().status == '前往巷口左转'
    assert op.steps == 2


def test_turn_probe_then_forward(op: BagelNavigate, monkeypatch: pytest.MonkeyPatch) -> None:
    """停车转镜头后短按 W，再用更新后的角色箭头核验转幅。"""
    op = published_navigation(op.ctx, action='approach')
    monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    learn = MagicMock()
    monkeypatch.setattr(op.turn_compensator, 'learn', learn)
    assert op.move_to_target().status.startswith('停车转向')
    op.ctx.controller.turn_by_angle_diff.assert_called_once_with(90)
    op.ctx.controller.move_w.assert_not_called()
    op.last_screenshot_time += 1
    assert op.move_to_target().status == '短按W后等待箭头对齐'
    learn.assert_not_called()
    op.last_screenshot_time += 1
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 270)
    assert op.move_to_target().status == '前往轮胎旁武备箱前'
    learn.assert_called_once_with(0, 90, 90)
    assert op.pending_turn is None
    op.ctx.controller.start_moving_forward.assert_called_once()
    assert op.steps == 2


def test_budget_includes_heading_probe(op: BagelNavigate) -> None:
    """动作耗尽后连校准短步也不允许。"""
    op.heading_aligned = False
    op.steps = op._action_limit()
    assert op.move_to_target().is_fail
    op.ctx.controller.move_w.assert_not_called()


def test_cruise_holds_without_counting_steps(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """远段朝向已对齐时按住前进，不把观察轮计入动作上限。"""
    monkeypatch.setattr(op.vision, 'locate', lambda _: (90, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    op.steps = 60
    assert op.move_to_target().status == '前往巷口左转'
    op.ctx.controller.start_moving_forward.assert_called_once()
    op.ctx.controller.move_w.assert_not_called()
    assert op.steps == 60


def test_small_heading_error_turns_while_holding(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """45° 以内边走边转，单次不超过 30°，并计入动作。"""
    op = published_navigation(op.ctx, action='approach')
    monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 300)
    assert op.move_to_target().status.startswith('行进转向')
    op.ctx.controller.start_moving_forward.assert_called_once()
    op.ctx.controller.turn_by_angle_diff.assert_called_once_with(30)
    assert op.steps == 1
    op.last_screenshot_time += 1
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 270)
    assert op.move_to_target().status == '前往轮胎旁武备箱前'
    assert op.pending_turn is None
    assert op.steps == 1


def test_large_heading_error_still_stops(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超过 45° 先松键再停车转，不按住前进。"""
    monkeypatch.setattr(op.vision, 'locate', lambda _: (90, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 90)
    assert op.move_to_target().status.startswith('停车转向')
    op.ctx.controller.stop_moving_forward.assert_called()
    op.ctx.controller.start_moving_forward.assert_not_called()
    assert abs(op.ctx.controller.turn_by_angle_diff.call_args.args[0]) <= 90


@pytest.mark.parametrize('reason', ['insufficient_geometry', 'ambiguous_position', 'outside_coverage', 'invalid_crop'])
def test_roadside_pickup_never_moves_without_location(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch, reason: str,
) -> None:
    """已定位后丢失位置，即使有路边 F 提示也必须松键，三次等待后停止。"""
    monkeypatch.setattr(op.vision, 'locate', lambda _: None)
    op.last_position = (50.0, 100.0)
    op.vision.last_location = MapLocation(None, op.vision.map.version, reason, '', 0, None, 0)

    def find_area(_screen: object, _screen_name: str, area_name: str) -> OperationRoundResult:
        if area_name in {'按键-普通攻击', '交互F键'}:
            return op.round_success()
        return op.round_fail()

    monkeypatch.setattr(op, 'round_by_find_area', find_area)
    op.heading_aligned = True
    for _ in range(3):
        result = op.move_to_target()
        assert result.result == OperationRoundResultEnum.WAIT
        assert result.status == '小地图暂时对不上，再看一帧'
        op.ctx.controller.stop_moving_forward.assert_called()
        op.ctx.controller.start_moving_forward.assert_not_called()
    assert op.move_to_target().is_fail
    op.ctx.controller.start_moving_forward.assert_not_called()
    for key in 'wasd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()
    assert op.ctx.controller.turn_by_angle_diff.call_count == 0


def test_roadside_pickup_resumes_only_after_location_recovers(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """定位恢复前不前进；恢复后按新位置继续，清零连续失配次数。"""
    positions = iter([(50.0, 100.0), None, (55.0, 100.0)])
    monkeypatch.setattr(op.vision, 'locate', lambda _: next(positions))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area in ('按键-普通攻击', '交互F键') else op.round_fail()
    ))
    assert op.move_to_target().status == '忽略路上可拾取物'
    op.ctx.controller.start_moving_forward.reset_mock()
    assert op.move_to_target().status == '小地图暂时对不上，再看一帧'
    op.ctx.controller.start_moving_forward.assert_not_called()
    op.ctx.controller.stop_moving_forward.assert_called()
    assert op.move_to_target().status == '忽略路上可拾取物'
    op.ctx.controller.start_moving_forward.assert_called_once()
    assert op.last_position == (55.0, 100.0)
    assert op.locate_misses == 0


def test_one_miss_after_a_fix_waits_instead_of_stopping(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """刚定位成功后的单帧失败先松键再看，不立刻结束本段。"""
    positions: list[tuple[float, float] | None] = [(50.0, 100.0), None]
    monkeypatch.setattr(op.vision, 'locate', lambda _: positions.pop(0))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    assert op.move_to_target().status == '前往巷口左转'
    op.ctx.controller.start_moving_forward.reset_mock()
    result = op.move_to_target()
    assert result.status == '小地图暂时对不上，再看一帧'
    assert not result.is_fail
    op.ctx.controller.stop_moving_forward.assert_called()
    op.ctx.controller.start_moving_forward.assert_not_called()


@pytest.mark.parametrize('recovers', [True, False])
def test_execute_roadside_pickup_waits_without_moving(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, recovers: bool,
) -> None:
    """完整执行链在路边拾取提示下停步换帧，定位恢复后到达或持续失配后失败。"""
    controller = FixtureController(test_context)
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r01-39s')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelNavigate', WatchedNavigate)
    op = published_navigation(test_context)
    positions = [(50.0, 100.0)] * 3 + [None] * (2 if recovers else 4)
    if recovers:
        positions.append((110.0, 100.0))
    observations: list[tuple[float, float] | None] = []

    def locate(_crop: object) -> tuple[float, float] | None:
        """每次真实截图后的定位返回下一份结果，旧坐标不能用于失配时前进。"""
        position = positions.pop(0)
        observations.append(position)
        return position

    def start_moving() -> None:
        """记录所有持续前进指令，直接拒绝没有当前坐标的移动。"""
        assert observations[-1] is not None
        controller.recorded_inputs.append('hold')

    monkeypatch.setattr(op.vision, 'locate', locate)
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area in ('按键-普通攻击', '交互F键') else op.round_fail()
    ))
    monkeypatch.setattr(controller, 'start_moving_forward', start_moving, raising=False)
    stop = MagicMock()
    monkeypatch.setattr(controller, 'stop_moving_forward', stop, raising=False)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success == recovers, result.status
        assert result.status == (op.STATUS_WAYPOINT if recovers else '小地图定位失败，停止移动')
        assert observations.count(None) == (2 if recovers else 4)
        assert controller.recorded_inputs.count('hold') == 1
        stop.assert_called()
        assert not positions
    finally:
        reset_running_state(test_context, op)


def test_repeated_locate_misses_still_stop(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """连续对不上超过允许帧数后仍然停止。"""
    monkeypatch.setattr(op.vision, 'locate', lambda _: None)
    op.last_position = (50.0, 100.0)
    op.locate_misses = 3
    result = op.move_to_target()
    assert result.is_fail and '小地图定位失败' in result.status


def test_weapon_box_prompt_is_not_a_roadside_pickup(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """去电子保险箱时，武备箱的 F 提示不能当成路上可拾取物盲走。"""
    test_context.mock_screen('贝果-局内', '雅努斯出生-r01-39s')
    op = published_navigation(test_context, target='safe', role='entry')
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', MagicMock(), raising=False)
    monkeypatch.setattr(test_context.controller, 'start_moving_forward', MagicMock(), raising=False)
    monkeypatch.setattr(op.vision, 'locate', lambda _: None)

    def find_area(_screen: object, _screen_name: str, area_name: str):
        if area_name in {'按键-普通攻击', '交互F键', '武备箱交互'}:
            return op.round_success()
        return op.round_fail()

    monkeypatch.setattr(op, 'round_by_find_area', find_area)
    op.heading_aligned = True
    result = op.move_to_target()
    assert result.is_fail and '小地图定位失败' in result.status
    op.ctx.controller.start_moving_forward.assert_not_called()


@pytest.mark.parametrize('image_angle,expected_mouse_sign', [(0, -1), (180, 1)])
def test_turn_reaches_mouse_with_correct_sign(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
    image_angle: float, expected_mouse_sign: int,
) -> None:
    """接通真实控制器的角度换算，左右转都必须发出正确鼠标位移。"""
    op = published_navigation(op.ctx, action='approach')
    monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: image_angle)
    controller = MagicMock()
    controller.game_config.turn_dx = -5.5
    controller.turn_by_angle_diff.side_effect = lambda angle: ZPcController.turn_by_angle_diff(controller, angle)
    op.turn_compensator.controller = controller
    assert op.move_to_target().status.startswith('停车转向')
    assert controller.turn_by_distance.call_args.args[0] * expected_mouse_sign > 0


@pytest.mark.parametrize('initial,target', [(0, 270), (180, 270), (350, 10), (10, 350)])
def test_turn_converges_with_controller_feedback(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch, initial: float, target: float,
) -> None:
    """鼠标转向不足时仍能收敛，覆盖左右和跨零度，旧符号会耗尽动作。"""
    heading = initial
    controller = MagicMock()
    controller.game_config.turn_dx = -5.5

    def move_mouse(distance: float) -> None:
        """模拟实机鼠标正位移使图像角度增加，实际转幅约为指令一半。"""
        nonlocal heading
        heading = (heading + distance / 5.5 * 0.55) % 360

    controller.turn_by_distance.side_effect = move_mouse
    controller.turn_by_angle_diff.side_effect = lambda angle: ZPcController.turn_by_angle_diff(controller, angle)
    op.turn_compensator.controller = controller
    op.vision.waypoints = [('测试目标', (20 * cos(radians(target)), 20 * sin(radians(target))))]
    op.active_waypoints = op.vision.waypoints
    monkeypatch.setattr(op.vision, 'locate', lambda _: (0, 0))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: heading)
    for _ in range(60):
        # 本例只模拟转向、不模拟行走位移，使用正常观测间隔以免触发三秒卡位保护。
        op.last_screenshot_time += 0.15
        result = op.move_to_target()
        if result.status == '前往测试目标' or result.is_fail:
            break
    assert result.status == '前往测试目标'
    assert op.steps < 20
    assert op.turn_compensator.scale > 1
    assert all(abs(call.args[0]) <= 90 for call in controller.turn_by_angle_diff.call_args_list)


def test_pause_discards_alignment(op: BagelNavigate) -> None:
    """暂停后释放按键，并废弃尚未校准的转向样本。"""
    op.pending_turn = (0, -30)
    op.handle_pause()
    assert not op.heading_aligned
    assert op.pending_turn is None
    op.ctx.controller.stop_moving_forward.assert_called_once()
    assert op.move_to_target().status == '短按W后等待箭头对齐'


def test_turn_probe_forward_flow(
    op: BagelNavigate, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """镜头转动后短步刷新箭头；仍未对准时再次转向并校准。"""
    controller = NavigationController(test_context)
    controller.set_phases([
        *[{'frame': ('贝果-局内', '雅努斯出生-r01-39s')} for _ in range(4)],
        {'frame': ('贝果-局内', '雅努斯箱前-r07-32s')},
    ])
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelNavigate', WatchedNavigate)
    navigation = published_navigation(test_context, action='approach')
    monkeypatch.setattr(
        navigation.vision, 'locate',
        lambda _: (110.0, 84.0) if controller.phase_idx == 4 else (110.0, 100.0),
    )
    monkeypatch.setattr(
        navigation.vision, 'player_angle', lambda _: 270 if controller.phase_idx == 4 else 0,
    )
    enter_running_state(test_context)
    try:
        result = navigation.execute()
        assert result.success and result.status == BagelNavigate.STATUS_ARRIVED_BOX
        assert controller.recorded_inputs == ['turn', 'w', 'turn', 'w']
        assert controller.phase_idx == 4
        assert not navigation.heading_aligned
    finally:
        reset_running_state(test_context, navigation)


def test_box_prompt_appears_during_stop(
    op: BagelNavigate, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """箱前短暂没有提示时只等新画面，提示出现立即成功，不盲走。"""
    op = published_navigation(op.ctx, action='approach')
    monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 84))
    assert op.move_to_target().status == '目标前停步等待交互提示'
    test_context.mock_screen('贝果-局内', '雅努斯箱前-r07-32s')
    op.screenshot()
    assert op.move_to_target().status == BagelNavigate.STATUS_ARRIVED_BOX
    for key in 'wasd':
        getattr(op.ctx.controller, f'move_{key}').assert_not_called()


def test_b_spawn_uses_position_and_stops_at_prompt(
    op: BagelNavigate, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B 按路点距离移动，改变位置会改变转向；丢定位松键，真提示才成功。"""
    test_context.mock_screen('贝果-局内', '白鸽工地出生-20260921-seq5s')
    # 固定本场景的目标坐标，发布路线微调不应改变这里核对的转角。
    flow = load_published_flow('janus_high_b')
    step = next(step for step in flow.steps if step.action == 'approach')
    step = replace(step, waypoints=(replace(step.waypoints[0], xy=(130.5, 69.4)),))
    navigation = BagelRunFlow(test_context, flow).build_operation(step)
    navigation.handle_init()
    navigation.screenshot()
    assert navigation.check_start().status == '开始移动'
    navigation.heading_aligned = True
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (100, 100))
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    first = navigation.move_to_target()
    assert first.status.startswith('停车转向')
    # 方向由目标 (130.5,69.4) 决定，不再使用旧 310 度。
    angle = test_context.controller.turn_by_angle_diff.call_args.args[0]
    assert 45 < angle < 46
    navigation.last_screenshot_time += 1
    assert navigation.move_to_target().status == '短按W后等待箭头对齐'
    navigation.last_screenshot_time += 1
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 315)
    assert navigation.move_to_target().status == '前往白鸽武备箱前'
    test_context.controller.start_moving_forward.assert_called()
    # 到箱前改短步，经过多少秒不影响判据。
    navigation.last_screenshot_time += 10
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (127, 73))
    test_context.controller.move_w.reset_mock()
    assert navigation.move_to_target().status == '前往白鸽武备箱前'
    test_context.controller.move_w.assert_called_once_with(press=True, press_time=0.2, release=True)
    navigation.last_screenshot_time += 1
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: None)
    test_context.controller.start_moving_forward.reset_mock()
    assert navigation.move_to_target().status == '小地图暂时对不上，再看一帧'
    test_context.controller.stop_moving_forward.assert_called()
    test_context.controller.start_moving_forward.assert_not_called()
    root = next(p for p in Path(__file__).resolve().parents if p.name == 'zzz-od-test')
    test_context.add_mock_screenshot(cv2_utils.read_image(str(root / 'screens/贝果-局内/白鸽工地箱前-录像8s.webp')))
    navigation.screenshot()
    navigation.last_screenshot_time = navigation.last_input_frame + 1
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (130.5, 69.4))
    assert navigation.move_to_target().status == BagelNavigate.STATUS_ARRIVED_BOX


def test_b_edited_waypoint_changes_steering(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """注入不同草稿时真实转向随目标改变，不受出生地专用朝向控制。"""
    from dataclasses import replace

    flow = load_published_flow('janus_high_b')
    step = next(step for step in flow.steps if step.action == 'approach')
    turns = []
    for target in ((130, 70), (130, 110)):
        changed = replace(step, waypoints=(replace(step.waypoints[0], xy=target),))
        draft = replace(flow, steps=tuple(changed if item.id == step.id else item for item in flow.steps))
        navigation = BagelRunFlow(op.ctx, draft).build_operation(changed)
        assert isinstance(navigation, BagelNavigate)
        navigation.handle_init()
        navigation.last_screenshot = op.last_screenshot
        navigation.last_screenshot_time = op.last_screenshot_time
        navigation.heading_aligned = True
        monkeypatch.setattr(navigation.vision, 'locate', lambda _: (100, 100))
        monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
        navigation.move_to_target()
        turns.append(op.ctx.controller.turn_by_angle_diff.call_args.args[0])
    assert turns[0] > 0 and turns[1] < 0


def test_safe_route_walks_then_uses_small_steps(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正式远段按住前进，独立靠近步骤朝目的地碎步，到点停下等待提示。"""
    navigation = published_navigation(op.ctx, target='safe', role='entry')
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (140, 80))
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    assert navigation.move_to_target().status == '前往电子保险箱巷口转向'
    op.ctx.controller.start_moving_forward.assert_called_once()
    op.ctx.controller.move_w.assert_not_called()
    assert navigation.steps == 0
    op.ctx.controller.start_moving_forward.reset_mock()
    navigation.last_screenshot_time += 1
    # 距入口超过到达半径仍按住，不改成 0.2 秒短步。
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (156, 84.9))
    assert navigation.move_to_target().status == '前往电子保险箱巷口转向'
    op.ctx.controller.start_moving_forward.assert_called_once()
    op.ctx.controller.move_w.assert_not_called()
    op.ctx.controller.start_moving_forward.reset_mock()
    navigation = published_navigation(op.ctx, action='approach', target='safe')
    navigation.steps = 60
    navigation.last_screenshot_time += 1
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (213, 110))
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    assert navigation.move_to_target().status == '前往电子保险箱前'
    op.ctx.controller.move_w.assert_called_once_with(press=True, press_time=0.08, release=True)
    op.ctx.controller.move_w.reset_mock()
    for position in ((214, 110), (215, 110)):
        navigation.last_screenshot_time += 1
        monkeypatch.setattr(navigation.vision, 'locate', lambda _, p=position: p)
        assert navigation.move_to_target().status == '前往电子保险箱前'
        op.ctx.controller.move_w.assert_called_once_with(press=True, press_time=0.08, release=True)
        op.ctx.controller.move_w.reset_mock()
    navigation.last_screenshot_time += 1
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: navigation.active_waypoints[-1][1])
    monkeypatch.setattr(navigation, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(navigation, 'round_by_find_area',
                        lambda *args: navigation.round_fail() if args[-1] == '交互F键' else navigation.round_success())
    assert navigation.move_to_target().status == '目标前停步等待交互提示'
    op.ctx.controller.move_w.assert_not_called()
    navigation.last_screenshot_time += 1
    navigation.steps = 100
    monkeypatch.setattr(navigation, 'round_by_find_area', lambda *_: navigation.round_success())
    assert navigation.move_to_target().status == BagelNavigate.STATUS_ARRIVED_SAFE
    op.ctx.controller.move_w.assert_not_called()


@pytest.mark.parametrize('role,position,angle,arrived', [
    ('entry', (160, 92), 0, False),
    ('entry', (178.6, 84.9), 0, True),
    ('entry', (194.6, 84.9), 0, True),
    ('turn', (194, 100), 40, False),
    ('turn', (186.6, 84.9), 30, False),
])
def test_safe_corner_turns_while_moving(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
    role: str, position: tuple[float, float], angle: float, arrived: bool,
) -> None:
    """入口允许较宽到达范围，楼角不能抄近路；每个正式路点独立结束并松键。"""
    navigation = published_navigation(op.ctx, target='safe', role=role)
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: position)
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: angle)
    result = navigation.move_to_target()
    if arrived:
        assert result.status == BagelNavigate.STATUS_WAYPOINT
        op.ctx.controller.stop_moving_forward.assert_called()
        op.ctx.controller.turn_by_angle_diff.assert_not_called()
        op.ctx.controller.start_moving_forward.assert_not_called()
    else:
        assert result.status.startswith('行进转向')
        op.ctx.controller.start_moving_forward.assert_called_once()
        turned = op.ctx.controller.turn_by_angle_diff.call_args.args[0]
        assert 0 < abs(turned) <= 30
    op.ctx.controller.move_w.assert_not_called()


def test_safe_cruise_stops_when_position_does_not_change(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """楼角后持续按住前进却卡在原地时，应松键留现场。"""
    navigation = published_navigation(op.ctx, target='safe', role='approach')
    # 与目标保持持续前进所需的距离，避免路线微调后落入短步分支。
    target = navigation.active_waypoints[0][1]
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (target[0] - 12, target[1]))
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    assert navigation.move_to_target().status == '前往电子保险箱接近点'
    op.ctx.controller.start_moving_forward.assert_called()
    navigation.last_screenshot_time += 3.1
    result = navigation.move_to_target()
    assert result.result == OperationRoundResultEnum.FAIL
    assert result.status == '持续前进但位置未变化，停止移动'
    op.ctx.controller.stop_moving_forward.assert_called()


def test_safe_cruise_progress_resets_stall_timer(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """沿墙实际前进超过两像素时，不能将下一帧误判为卡位。"""
    navigation = published_navigation(op.ctx, target='safe', role='approach')
    position = [(180.3, 89.9)]
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: position[0])
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 72.5)
    assert navigation.move_to_target().result == OperationRoundResultEnum.WAIT
    position[0] = (182.5, 93)
    navigation.last_screenshot_time += 2.9
    assert navigation.move_to_target().result == OperationRoundResultEnum.WAIT
    navigation.last_screenshot_time += 0.2
    assert navigation.move_to_target().result == OperationRoundResultEnum.WAIT


def test_safe_approach_does_not_steer_away_from_right_wall(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """实机已靠到右墙后，后续路点不能把人向北拉回停车位。"""
    navigation = published_navigation(op.ctx, target='safe', role='approach')
    root = next(path for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')
    navigation.last_screenshot = cv2_utils.read_image(str(
        root / 'screens/贝果-局内/停车场已靠右墙-20260923-2106.webp',
    ))
    navigation.last_screenshot_time = op.last_screenshot_time
    navigation.heading_aligned = True
    # 2026-09-23 21:06 实机录像 177 秒：人已到右墙边，随后却走回道路。
    position = navigation.vision.locate(navigation.minimap())
    assert position is not None
    assert abs(position[0] - 192.92) < 1 and abs(position[1] - 108.71) < 1
    cruise = MagicMock(return_value=navigation.round_wait('记录方向'))
    monkeypatch.setattr(navigation, '_cruise_toward', cruise)
    navigation.move_to_target()
    assert cruise.call_count == 1
    target_angle = cruise.call_args.args[1]
    assert target_angle >= 270 or target_angle <= 5, f'不应向北离墙：{target_angle:.1f}度'


def test_safe_does_not_start_small_steps_in_parking_spaces(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧接近点在停车场里，不能在这里切换成最后碎步段。"""
    navigation = published_navigation(op.ctx, target='safe', role='approach')
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (201.67, 103.35))
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    result = navigation.move_to_target()
    assert result.result == OperationRoundResultEnum.WAIT
    assert navigation.coordinate_only
    op.ctx.controller.move_w.assert_not_called()


def test_safe_corner_releases_forward_before_next_segment(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """到新楼角点两像素内应先松键，再切换到接近段。"""
    navigation = published_navigation(op.ctx, target='safe', role='turn')
    x, y = navigation.active_waypoints[0][1]
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (x - 1, y))
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    result = navigation.move_to_target()
    assert result.status == BagelNavigate.STATUS_WAYPOINT
    op.ctx.controller.stop_moving_forward.assert_called()
    op.ctx.controller.start_moving_forward.assert_not_called()


def test_safe_brakes_before_final_steps_and_waits_for_new_frame(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回放第九步提前 5.73 像素松键：停稳后继续当前步，到达才完成。"""
    flow = load_published_flow('janus_high_a')
    step = replace(flow.steps[8], waypoints=(replace(
        flow.steps[8].waypoints[0], xy=(215.9, 109.9), tolerance=2, passed_tolerance=2,
    ),))
    navigation = BagelRunFlow(op.ctx, flow).build_operation(step)
    navigation.handle_init()
    navigation.screenshot()
    navigation.heading_aligned = True
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (210.1746, 109.7051))
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    assert navigation.move_to_target().result == OperationRoundResultEnum.WAIT
    op.ctx.controller.stop_moving_forward.assert_called()
    op.ctx.controller.move_w.assert_not_called()
    assert navigation.move_to_target().status == '等待动作后的新截图'
    navigation.last_screenshot_time += 0.2
    assert navigation.move_to_target().result == OperationRoundResultEnum.WAIT
    op.ctx.controller.move_w.assert_not_called()
    navigation.last_screenshot_time += 0.5
    assert navigation.move_to_target().result == OperationRoundResultEnum.WAIT
    op.ctx.controller.move_w.assert_called_once_with(press=True, press_time=0.2, release=True)
    # 仍在停车范围内，不能反复停车；继续短步调整。
    navigation.last_screenshot_time += 0.5
    assert navigation.move_to_target().result == OperationRoundResultEnum.WAIT
    assert op.ctx.controller.move_w.call_count == 2
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: (214.4, 109.9))
    navigation.last_screenshot_time += 0.5
    assert navigation.move_to_target().status == BagelNavigate.STATUS_WAYPOINT
    assert op.ctx.controller.move_w.call_count == 2
    op.ctx.controller.start_moving_forward.assert_not_called()


def test_braked_move_execute_waits_until_destination(
    op: BagelNavigate, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实执行循环不能在提前停车处结束；停稳、新截图、补步后才返回到达。"""
    controller = NavigationController(test_context)
    phases = [{'frame': ('贝果-局内', '雅努斯出生-r01-39s')} for _ in range(3)]
    controller.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelNavigate', WatchedNavigate)
    navigation = published_navigation(test_context, target='safe', role='approach')
    x, y = navigation.active_waypoints[0][1]
    positions = [(x - 5.73, y), (x - 3, y), (x - 1, y)]
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: positions[controller.phase_idx])
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    original_screenshot = navigation.screenshot
    polls = 0

    def screenshot_with_clock() -> None:
        """读取存档画面并推进截图时间，避免真实睡眠。"""
        nonlocal polls
        original_screenshot()
        polls += 1
        navigation.last_screenshot_time = polls * 0.3

    monkeypatch.setattr(navigation, 'screenshot', screenshot_with_clock)
    enter_running_state(test_context)
    try:
        result = navigation.execute()
        assert result.success and result.status == BagelNavigate.STATUS_WAYPOINT
        assert controller.phase_idx == 2
        assert controller.recorded_inputs == ['w', 'w']
    finally:
        reset_running_state(test_context, navigation)


def test_safe_final_steps_never_restart_cruise_on_pickup(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """末段即使有杂物提示且定位暂失，也不能恢复按住前进而冲过保险箱。"""
    navigation = published_navigation(op.ctx, action='approach', target='safe')
    navigation.last_position = (212, 110)
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: None)
    monkeypatch.setattr(navigation, '_ignoring_pickup', lambda: True)
    assert navigation.move_to_target().status == '小地图暂时对不上，再看一帧'
    op.ctx.controller.stop_moving_forward.assert_called()
    op.ctx.controller.start_moving_forward.assert_not_called()


@pytest.mark.parametrize('state,position,arrived', [
    ('电子保险箱仅名称', (218, 110), False),
    ('电子保险箱F提示', (218, 110), True),
    ('电子保险箱F提示', (100, 100), False),
    ('电子保险箱F提示', None, False),
])
def test_safe_prompt_requires_real_f_button(
    op: BagelNavigate, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    state: str, position: tuple[float, float] | None, arrived: bool,
) -> None:
    """正式靠近必须同时定位到目标附近并看到 F；只有名称或丢定位不能完成。"""
    test_context.mock_screen('贝果-局内', state)
    navigation = published_navigation(test_context, action='approach', target='safe')
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: position)
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: None)
    result = navigation.move_to_target()
    assert (result.status == navigation.STATUS_ARRIVED_SAFE) is arrived
    test_context.controller.move_w.assert_not_called()


def test_stationary_character_arrow_requires_probe_after_camera_turn(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """镜头转动不改变静止角色箭头，必须先短步再用新箭头核验。"""
    op = published_navigation(op.ctx, action='approach')
    monkeypatch.setattr(op.vision, 'locate', lambda _: (110, 100))
    character_angle = 0.0
    camera_angle = 0.0

    def turn(angle: float) -> None:
        nonlocal camera_angle
        camera_angle = (camera_angle - angle) % 360

    def walk(press: bool, press_time: float, release: bool) -> None:
        nonlocal character_angle
        character_angle = camera_angle

    op.ctx.controller.turn_by_angle_diff.side_effect = turn
    op.ctx.controller.move_w.side_effect = walk
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: character_angle)
    assert op.move_to_target().status.startswith('停车转向')
    op.last_screenshot_time += 1
    assert op.move_to_target().status == '短按W后等待箭头对齐'
    op.last_screenshot_time += 1
    assert op.move_to_target().status == '前往轮胎旁武备箱前'
    op.ctx.controller.turn_by_angle_diff.assert_called_once_with(90)


def test_passed_corner_advances_instead_of_spinning(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """越过拐点后目标在身后，切下一段，不停车转回去。"""
    # try077 巷口：一步从点前跨到 (112.1, 99.9)，偏差约 180°。
    monkeypatch.setattr(op.vision, 'locate', lambda _: (112.1, 99.9))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    op.heading_aligned = True
    assert op.move_to_target().status == BagelNavigate.STATUS_WAYPOINT
    op.ctx.controller.stop_moving_forward.assert_called()
    op.ctx.controller.turn_by_angle_diff.assert_not_called()


def test_corner_does_not_turn_two_pixels_early(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """实机距拐点约 1.8 像素仍被墙挡住，继续走近后才转向。"""
    monkeypatch.setattr(op.vision, 'locate', lambda _: (108.2, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    assert op.move_to_target().status == '前往巷口左转'
    assert op.waypoint_index == 0
    op.last_screenshot_time += 1
    monkeypatch.setattr(op.vision, 'locate', lambda _: (109.3, 100))
    assert op.move_to_target().status == BagelNavigate.STATUS_WAYPOINT
    op.ctx.controller.stop_moving_forward.assert_called()


@pytest.mark.parametrize('action', ['move', 'approach'])
def test_small_steps_recompute_heading_from_current_position(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch, action: str,
) -> None:
    """普通移动和靠近都能碎步，每次朝唯一目的地调整，远处也不持续按住。"""
    navigation = published_navigation(op.ctx, action=action)
    navigation.navigation = replace(navigation.navigation, final_mode='small_steps')
    monkeypatch.setattr(navigation, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(navigation, 'round_by_find_area',
                        lambda *args: navigation.round_success() if args[-1] == '按键-普通攻击' else navigation.round_fail())
    monkeypatch.setattr(navigation.vision, 'player_angle', lambda _: 0)
    align = MagicMock(return_value=None)
    monkeypatch.setattr(navigation, '_align_to_heading', align)
    x, y = navigation.active_waypoints[-1][1]
    for position, angle in [((x - 20, y), 0), ((x, y + 20), 90), ((x + 20, y), 180)]:
        monkeypatch.setattr(navigation.vision, 'locate', lambda _, p=position: p)
        navigation.last_screenshot_time += 1
        navigation.move_to_target()
        assert align.call_args.args[1] == pytest.approx(angle)
        op.ctx.controller.move_w.assert_called_with(press=True, press_time=0.08, release=True)
    assert op.ctx.controller.move_w.call_count == 3
    op.ctx.controller.start_moving_forward.assert_not_called()


@pytest.mark.parametrize('mode', ['coordinate', 'small_steps'])
@pytest.mark.parametrize('target', ['box', 'safe'])
@pytest.mark.parametrize('after_arrival', ['drift', 'lost', 'prompt', 'late_prompt'])
def test_reaching_point_waits_without_moving_then_succeeds_or_fails(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
    mode: str, target: str, after_arrival: str,
) -> None:
    """到点后定位漂移或丢失均不再走；两秒内有效提示可成功，否则失败。"""
    navigation = published_navigation(op.ctx, action='approach', target=target)
    navigation.navigation = replace(navigation.navigation, final_mode=mode)
    xy = navigation.active_waypoints[-1][1]
    monkeypatch.setattr(navigation, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(navigation, 'round_by_find_area',
                        lambda *args: navigation.round_success() if args[-1] == '按键-普通攻击' else navigation.round_fail())
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: xy)
    started = navigation.last_screenshot_time
    assert navigation.move_to_target().status == '目标前停步等待交互提示'
    if after_arrival == 'drift':
        monkeypatch.setattr(navigation.vision, 'locate', lambda _: (xy[0] + 5, xy[1]))
    elif after_arrival == 'lost':
        monkeypatch.setattr(navigation.vision, 'locate', lambda _: None)
    navigation.last_screenshot_time = started + 1
    assert navigation.move_to_target().status == '目标前停步等待交互提示'
    navigation.last_screenshot_time = started + 2.1
    if after_arrival == 'late_prompt':
        monkeypatch.setattr(navigation, 'round_by_find_area', lambda *_: navigation.round_success())
    if after_arrival == 'prompt':
        navigation.last_screenshot_time = started + 1.5
        monkeypatch.setattr(navigation, 'round_by_find_area', lambda *_: navigation.round_success())
        assert navigation.move_to_target().status == navigation.arrive_status
    else:
        result = navigation.move_to_target()
        assert result.result == OperationRoundResultEnum.FAIL
        assert '未发现' in result.status
    op.ctx.controller.move_w.assert_not_called()
    op.ctx.controller.start_moving_forward.assert_not_called()
    op.ctx.controller.stop_moving_forward.assert_called()


def test_plain_small_steps_finish_at_destination_without_prompt(
    op: BagelNavigate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无箱子和交互提示时，普通碎步到点即可结束。"""
    op.navigation = replace(op.navigation, final_mode='small_steps')
    monkeypatch.setattr(op.vision, 'locate', lambda _: op.active_waypoints[-1][1])
    assert op.move_to_target().status == op.STATUS_WAYPOINT
    op.ctx.controller.move_w.assert_not_called()
    op.ctx.controller.start_moving_forward.assert_not_called()


@pytest.mark.parametrize('mode', ['coordinate', 'small_steps'])
@pytest.mark.parametrize('prompt_appears', [False, True])
def test_arrival_wait_runs_with_real_frames_without_more_input(
    op: BagelNavigate, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    mode: str, prompt_appears: bool,
) -> None:
    """完整执行循环回放到点后等待和提示出现，时间推进不依赖实际睡眠。"""
    controller = NavigationController(test_context)
    phases = [{'frame': ('贝果-局内', '雅努斯出生-r01-39s'), 'exit': ('on_polls', 4)}]
    if prompt_appears:
        phases.append({'frame': ('贝果-局内', '雅努斯箱前-r07-32s')})
    controller.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelNavigate', WatchedNavigate)
    navigation = published_navigation(test_context, action='approach')
    navigation.navigation = replace(navigation.navigation, final_mode=mode)
    monkeypatch.setattr(navigation.vision, 'locate', lambda _: navigation.active_waypoints[-1][1])
    controller.set_phases(phases)
    original_screenshot = navigation.screenshot
    polls = 0

    def screenshot_with_clock() -> None:
        """保留真实画面读取，每次观察推进半秒供超时分支判断。"""
        nonlocal polls
        original_screenshot()
        polls += 1
        navigation.last_screenshot_time = polls * 0.5

    monkeypatch.setattr(navigation, 'screenshot', screenshot_with_clock)
    enter_running_state(test_context)
    try:
        result = navigation.execute()
        assert result.success == prompt_appears, result.status
        if prompt_appears:
            assert result.status == navigation.STATUS_ARRIVED_BOX
        else:
            assert '未发现武备箱交互' in result.status
        assert not controller.recorded_inputs
        assert polls >= 4
    finally:
        reset_running_state(test_context, navigation)
