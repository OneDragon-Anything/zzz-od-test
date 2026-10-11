"""到达动作（arrive_hook）闭环转向的测试（不依赖画面）。

2026-10-11 实机问题：到达动作靠纯计时推进（`move_d 0.2s` → `W+D 1.0s` → `W 0.8s`），
三段各切多少度全看代理人的转身动画速度，所以换个代理人转角就变、结果不稳。

改法：段内可以要求闭环转向（`heading` 写死角度，`heading_to_next` 由程序按下一路点
坐标算），该段就不再按时间收尾，而是每轮读角色箭头补转，进入死区才进下一段。
转的是镜头不是角色，所以与代理人无关。

这里只测解析、校验和执行分支，不读画面、不触盘。
"""

import pytest

from zzz_od.application.bagel.bagel_const import NAV_HOOK_HEADING_MISS_LIMIT
from zzz_od.application.bagel.bagel_flow import ArriveHook, ArriveHookStep
from zzz_od.application.bagel.bagel_navigate import BagelNavigate


class _RoundResult:
    """只带 status 的轮次结果替身。"""

    def __init__(self, status: str) -> None:
        self.status = status


class _StubController:
    """记录移动键与镜头转向。"""

    def __init__(self) -> None:
        self.held: list[str] = []
        self.released: list[str] = []
        self.turns: list[float] = []

    def __getattr__(self, name: str):
        def _press(press: bool = False, press_time=None, release: bool = False) -> None:
            if press:
                self.held.append(name)
            else:
                self.released.append(name)
        return _press

    def turn_by_angle_diff(self, angle_diff: float) -> None:
        self.turns.append(angle_diff)

    def turn_by_distance(self, d: float) -> None:
        self.turns.append(d)

    def stop_moving_forward(self) -> None:
        pass


class _StubCtx:
    def __init__(self) -> None:
        self.controller = _StubController()


class _StubCompensator:
    """转向补偿替身：记录下发的角度，不做真实鼠标移动。"""

    def __init__(self) -> None:
        self.issued: list[float] = []

    def turn(self, angle_diff: float, max_abs_angle_diff=None) -> float:
        effective = angle_diff
        if max_abs_angle_diff is not None:
            effective = max(-max_abs_angle_diff, min(effective, max_abs_angle_diff))
        self.issued.append(effective)
        return effective

    def learn(self, *args) -> None:
        pass


def _make_nav(
    hook_actions, waypoints: list[tuple[str, tuple[float, float]]],
    next_waypoint: tuple[float, float] | None = None,
):
    """建一个只够跑 hook 的导航实例。

    下一个步骤的路点要显式传入：每个移动步骤是独立操作实例，只带自己那段路点。
    """
    nav = BagelNavigate.__new__(BagelNavigate)
    nav.ctx = _StubCtx()
    nav.map_id = 'janus_high_c'
    nav.destination = 'move'
    nav.coordinate_only = True
    nav.arrive_hook = ArriveHook(tuple(hook_actions))
    nav.active_waypoints = waypoints
    nav.next_waypoint = next_waypoint
    nav.waypoint_index = 0
    nav.last_position = (0.0, 0.0)
    nav.pending_turn = None
    nav.heading_aligned = True
    nav.last_input_frame = None
    nav.last_screenshot_time = 0.0
    nav._hook_started = False
    nav._hook_queue = tuple(hook_actions)
    nav._hook_index = 0
    nav._hook_left = 0.0
    nav._held_move_keys = ()
    nav._hook_heading = None
    nav._hook_heading_misses = 0
    nav._record_input = lambda: None
    return nav


class TestArriveHookParse:
    """``heading`` / ``heading_to_next`` 的解析与校验。"""

    def test_plain_step_stays_timing_only(self) -> None:
        """不写转向的段保持纯计时，不受影响。"""
        step = ArriveHook._parse_step({'keys': ['move_w'], 'seconds': 0.8})
        assert step.heading is None
        assert step.heading_to_next is False
        assert not step.uses_heading()

    def test_heading_to_next_parsed(self) -> None:
        step = ArriveHook._parse_step(
            {'keys': ['move_w', 'move_d'], 'seconds': 1.0, 'heading_to_next': True},
        )
        assert step.heading_to_next
        assert step.uses_heading()

    def test_heading_angle_parsed(self) -> None:
        step = ArriveHook._parse_step(
            {'keys': ['move_w'], 'seconds': 1.0, 'heading': 90.0},
        )
        assert step.heading == 90.0
        assert not step.heading_to_next
        assert step.uses_heading()

    def test_heading_and_to_next_are_exclusive(self) -> None:
        """两个字段同时写属于配置矛盾，必须报错而不是悄悄取一个。"""
        with pytest.raises(ValueError, match='不能同时指定'):
            ArriveHook._parse_step(
                {'keys': ['move_w'], 'seconds': 1.0, 'heading': 90.0, 'heading_to_next': True},
            )

    @pytest.mark.parametrize('angle', [400.0, -400.0])
    def test_heading_out_of_range_rejected(self, angle: float) -> None:
        with pytest.raises(ValueError):
            ArriveHook._parse_step(
                {'keys': ['move_w'], 'seconds': 1.0, 'heading': angle},
            )

    def test_round_trip_keeps_only_declared_fields(self) -> None:
        """回写不能把「转向下一路点」的内部占位值当heading 写出去。"""
        step = ArriveHook._parse_step(
            {'keys': ['move_w'], 'seconds': 1.0, 'heading_to_next': True},
        )
        assert step.to_dict() == {
            'keys': ['move_w'], 'seconds': 1.0, 'heading_to_next': True,
        }


class TestHookNextWaypointHeading:
    """``heading_to_next`` 的角度换算。

    公式必须与导航主循环逐字一致（``atan2(position - target)``）。这套公式给出的是
    「从目标看向角色」的反向向量，看着和直觉相反，但导航一直这么算且实机跑通；
    一旦写成 ``target - position``，角度差 180 度，delta 符号随之反转，
    2026-10-11 实机表现为该右转却往左转。
    """

    def test_target_to_the_east_is_one_eighty(self) -> None:
        nav = _make_nav(
            [ArriveHookStep(('move_w',), 1.0, heading_to_next=True)],
            [('当前', (0.0, 0.0))],
            next_waypoint=(10.0, 0.0),
        )
        assert nav._next_waypoint_heading() == pytest.approx(180.0)

    def test_target_to_the_south_is_two_seventy(self) -> None:
        """下一路点在正南（y 增大）时得到 270 度，与正东的 180 度差 90 度。"""
        nav = _make_nav(
            [ArriveHookStep(('move_w',), 1.0, heading_to_next=True)],
            [('当前', (0.0, 0.0))],
            next_waypoint=(0.0, 10.0),
        )
        assert nav._next_waypoint_heading() == pytest.approx(270.0)

    def test_north_is_exactly_opposite_of_south(self) -> None:
        """正北与正南必须差 180 度，防止 y 的符号再写反。"""
        def angle_for(target: tuple[float, float]) -> float:
            nav = _make_nav(
                [ArriveHookStep(('move_w',), 1.0, heading_to_next=True)],
                [('当前', (0.0, 0.0))],
                next_waypoint=target,
            )
            return nav._next_waypoint_heading()

        assert abs(angle_for((0.0, 10.0)) - angle_for((0.0, -10.0))) == pytest.approx(180.0)

    def test_no_next_waypoint_returns_none(self) -> None:
        """流程里没有下一个移动步骤时算不出方向，必须退回纯计时而不是转错方向。"""
        nav = _make_nav(
            [ArriveHookStep(('move_w',), 1.0, heading_to_next=True)],
            [('当前', (0.0, 0.0))],
        )
        assert nav._next_waypoint_heading() is None

    def test_without_position_returns_none(self) -> None:
        """还没定位到当前位置时也算不出方向，同样退回纯计时。"""
        nav = _make_nav(
            [ArriveHookStep(('move_w',), 1.0, heading_to_next=True)],
            [('当前', (0.0, 0.0))],
            next_waypoint=(0.0, 10.0),
        )
        nav.last_position = None
        assert nav._next_waypoint_heading() is None


class TestHookClosedLoopTurn:
    """闭环转向的执行分支。"""

    def _nav_with_angle(self, image_angle: float | None):
        nav = _make_nav(
            [ArriveHookStep(('move_w', 'move_d'), 1.0, heading_to_next=True)],
            [('当前', (0.0, 0.0))],
            next_waypoint=(0.0, 10.0),  # 目标南向 90
        )
        nav.vision = type('_V', (), {
            'player_angle': staticmethod(lambda crop: image_angle),
        })()
        nav.minimap = lambda: None
        nav.turn_compensator = _StubCompensator()
        return nav

    def test_aligned_turn_finishes_immediately(self) -> None:
        """朝向已对齐时本段立刻结束，不再多转。"""
        nav = self._nav_with_angle(-90.0)  # 图像角 -90 → 控制角 90
        nav._hook_heading = 90.0
        assert nav._hook_turn_done() is True
        assert nav.turn_compensator.issued == []

    def test_off_angle_issues_turn_and_stays(self) -> None:
        """朝向没对齐时下发转向，并保持本段继续。"""
        nav = self._nav_with_angle(0.0)  # 控制角 0，与目标 90 差 90
        nav._hook_heading = 90.0
        assert nav._hook_turn_done() is False
        assert nav.turn_compensator.issued
        assert nav.pending_turn is not None

    def test_missing_arrow_gives_up_after_limit(self) -> None:
        """连续读不到箭头到上限就放弃转向，不能把路线卡死。"""
        nav = self._nav_with_angle(None)
        nav._hook_heading = 90.0
        for _ in range(NAV_HOOK_HEADING_MISS_LIMIT - 1):
            assert nav._hook_turn_done() is False
        # 第 LIMIT 帧才放弃：容错窗口内继续等，不因偶发丢帧就放弃转向。
        assert nav._hook_turn_done() is True
        assert nav._hook_heading is None

    def test_single_miss_does_not_give_up(self) -> None:
        """偶发一帧读不到不算放弃，转向继续。"""
        nav = self._nav_with_angle(None)
        nav._hook_heading = 90.0
        assert nav._hook_turn_done() is False
        assert nav._hook_heading == 90.0

    def test_starts_next_step_with_resolved_heading(self) -> None:
        """切到下一段时重新按该段配置算转向目标，不会串用上一段的。"""
        nav = _make_nav(
            [
                ArriveHookStep(('move_d',), 0.2),
                ArriveHookStep(('move_w', 'move_d'), 1.0, heading_to_next=True),
            ],
            [('当前', (0.0, 0.0))],
            next_waypoint=(10.0, 0.0),  # 正东 → 导航公式给 180
        )
        nav._record_input = lambda: None
        nav.round_wait = lambda status, wait=None, **kw: _RoundResult(status)
        first = nav._start_hook_step()
        assert nav._hook_heading is None  # 第一段没写转向
        assert '按住' in first.status

        nav._hook_index = 1
        second = nav._start_hook_step()
        assert nav._hook_heading == pytest.approx(180.0)
        assert '转到' in second.status