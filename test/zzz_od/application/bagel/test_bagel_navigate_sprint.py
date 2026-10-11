"""每个路点只点一次冲刺的测试（不依赖画面）。

2026-10-11 实机日志暴露的问题：`_start_forward` 每隔 1 秒（``NAV_SPRINT_REPEAT_GAP``）
就会补按一次冲刺键，冲刺惯性一路累积，把西南转角冲出目标 9.9 格，``arrive_hook``
落点方向整个反掉，下一个路点直接卡死失败。

改法：记录「已经给第几个路点点过冲刺」，每个路点只点一次，换路点才允许再点。

这里只测 ``_start_forward`` 的按键次数，不读画面、不触盘。
"""

import pytest

from zzz_od.application.bagel.bagel_flow import NavigationOptions
from zzz_od.application.bagel.bagel_navigate import BagelNavigate


class _CountingController:
    """只记录前进与冲刺的按下次数。"""

    def __init__(self) -> None:
        self.forward_count: int = 0
        self.sprint_count: int = 0

    def start_moving_forward(self) -> None:
        self.forward_count += 1

    def stop_moving_forward(self) -> None:
        pass

    def start_sprinting_forward(self) -> None:
        self.sprint_count += 1


class _StubCtx:
    """只提供 ``controller``，够 ``_start_forward`` 用。"""

    def __init__(self) -> None:
        self.controller = _CountingController()


def _make_nav(sprint: bool | None = None, waypoints: int = 1) -> tuple[BagelNavigate, _CountingController]:
    """建一个只够跑 ``_start_forward`` 的导航实例。

    ``__new__`` 绕过 ``__init__``（后者要完整执行环境、底图和操作框架），再手工注入
    本测试关心的四个字段。
    """
    nav = BagelNavigate.__new__(BagelNavigate)
    ctx = _StubCtx()
    nav.ctx = ctx
    nav.navigation = NavigationOptions(sprint=sprint)
    nav.map_id = 'janus_high_c'
    nav.destination = 'move'
    nav.waypoint_index = 0
    nav._sprint_waypoint_index = None
    nav.active_waypoints = [(f'路点{i}', (0.0, 0.0)) for i in range(waypoints)]
    return nav, ctx.controller


class TestSprintOncePerWaypoint:
    """``_start_forward`` 的冲刺次数。"""

    def test_repeated_calls_sprint_only_once(self) -> None:
        """同一路点内连按十次前进，冲刺只点一次。"""
        nav, controller = _make_nav()

        for _ in range(10):
            nav._start_forward()

        assert controller.forward_count == 10
        assert controller.sprint_count == 1

    def test_next_waypoint_sprints_again(self) -> None:
        """换到下一个路点后允许再点一次冲刺。"""
        nav, controller = _make_nav(waypoints=2)

        nav._start_forward()
        nav._start_forward()
        assert controller.sprint_count == 1

        nav.waypoint_index = 1
        nav._start_forward()
        nav._start_forward()

        assert controller.forward_count == 4
        assert controller.sprint_count == 2

    def test_handle_init_reset_allows_sprint_again(self) -> None:
        """重新执行（handle_init 重置计数器）后允许再点冲刺。

        ``waypoint_index`` 在真实流程里只增不减，所以实现只记「已点过的是第几个
        路点」这一个数；换局重跑靠 ``handle_init`` 把计数器清空来放行。
        """
        nav, controller = _make_nav()

        nav._start_forward()
        assert controller.sprint_count == 1

        # handle_init 里的重置动作（handle_init 本身要完整执行环境，这里只验证它改的字段）
        nav._sprint_waypoint_index = None
        nav._start_forward()

        assert controller.sprint_count == 2

    def test_sprint_disabled_never_sprints(self) -> None:
        """``sprint: false`` 的步骤一次都不点冲刺，但前进照常按。"""
        nav, controller = _make_nav(sprint=False)

        for _ in range(5):
            nav._start_forward()

        assert controller.forward_count == 5
        assert controller.sprint_count == 0

    @pytest.mark.parametrize('waypoints', [1, 2, 3])
    def test_每路点恰好一次(self, waypoints: int) -> None:
        """整段跑完：每个路点各点一次冲刺，总次数等于路点数。"""
        nav, controller = _make_nav(waypoints=waypoints)

        for index in range(waypoints):
            nav.waypoint_index = index
            for _ in range(4):
                nav._start_forward()

        assert controller.sprint_count == waypoints