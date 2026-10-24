from pathlib import Path

import pytest
from cv2.typing import MatLike
from test.conftest import TestContext as FixtureTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import cv2_utils
from zzz_od.config.team_config import PredefinedTeamInfo, TeamConfig
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam

SCREEN_ROOT = Path(__file__).resolve().parents[4] / 'screens'
TEAM_ONE_CARD_RECT: tuple[int, int, int, int] = (140, 110, 960, 395)


class _WatchedChoosePredefinedTeam(WatchdogOperationMixin, ChoosePredefinedTeam):
    """带轮次上限的预备编队选择操作。"""

    watchdog_max_rounds: int = 30


def load_screen(screen_name: str, state: str) -> MatLike:
    """读取预备编队流程的画面存档。"""
    image = cv2_utils.read_image(str(SCREEN_ROOT / screen_name / f'{state}.webp'))
    assert image is not None
    return image


@pytest.fixture
def predefined_team(monkeypatch: pytest.MonkeyPatch) -> PredefinedTeamInfo:
    """固定第一个预备编队的名称，避免读取用户配置。"""
    team = PredefinedTeamInfo(
        idx=0,
        name='编队1',
        auto_battle='全配队通用',
        agent_id_list=[],
    )

    def get_team_list(_config: TeamConfig) -> list[PredefinedTeamInfo]:
        """返回流程截图中的第一支编队。"""
        return [team]

    monkeypatch.setattr(TeamConfig, 'team_list', property(get_team_list))
    return team


@pytest.fixture
def operation(
        test_context: FixtureTestContext,
        predefined_team: PredefinedTeamInfo,
) -> ChoosePredefinedTeam:
    """创建选择第一支编队的实际操作。"""
    return ChoosePredefinedTeam(test_context, [predefined_team.idx])


@pytest.fixture
def fixture_controller(
        test_context: FixtureTestContext,
        monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """给完整流程注入会按点击切换画面的控制器。"""
    controller = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )

    def ignore_mouse_move(_pos: Point) -> None:
        """测试控制器不需要真的移动鼠标。"""

    monkeypatch.setattr(controller, 'mouse_move', ignore_mouse_move, raising=False)
    monkeypatch.setattr(test_context, 'controller', controller)
    return controller


def get_predefined_deploy_area(test_context: FixtureTestContext) -> ScreenArea:
    """获取所有选队状态机共用的预备出战区域。"""
    area = test_context.screen_loader.get_area('实战模拟室', '预备出战')
    assert area is not None
    return area


def test_predefined_deploy_uses_exact_white_text(
        test_context: FixtureTestContext,
) -> None:
    """预备出战区域必须完整匹配白色启用文字。"""
    area = get_predefined_deploy_area(test_context)

    assert area.text == '预备出战'
    assert area.lcs_percent == 1.0
    assert area.color_range == [[240, 240, 240], [255, 255, 255]]


def test_choose_team_selects_target_while_confirm_is_disabled(
        test_context: FixtureTestContext,
        monkeypatch: pytest.MonkeyPatch,
        operation: ChoosePredefinedTeam,
) -> None:
    """确认按钮为灰色时应选择目标队伍，不得提前进入确认节点。"""
    clicked_points: list[Point] = []

    def record_click(
            pos: Point | None = None,
            press_time: float = 0,
            pc_alt: bool = False,
            gamepad_key: str | None = None,
    ) -> bool:
        """记录选队节点发出的点击位置。"""
        if pos is not None:
            clicked_points.append(pos)
        return True

    monkeypatch.setattr(test_context.controller, 'click', record_click)
    test_context.add_mock_screenshot(load_screen('预备编队', '未选择'))
    operation.screenshot()

    result = operation.choose_team()

    assert result.result == OperationRoundResultEnum.WAIT
    assert clicked_points


def test_click_confirm_accepts_enabled_button(
        test_context: FixtureTestContext,
        monkeypatch: pytest.MonkeyPatch,
        operation: ChoosePredefinedTeam,
) -> None:
    """白色启用按钮应让实际确认节点完成点击。"""
    clicked_points: list[Point] = []

    def record_click(
            pos: Point | None = None,
            press_time: float = 0,
            pc_alt: bool = False,
            gamepad_key: str | None = None,
    ) -> bool:
        """记录确认节点发出的点击位置。"""
        if pos is not None:
            clicked_points.append(pos)
        return True

    def ignore_mouse_move(_pos: Point) -> None:
        """节点点击成功后不需要真的移动鼠标。"""

    monkeypatch.setattr(test_context.controller, 'click', record_click)
    monkeypatch.setattr(
        test_context.controller,
        'mouse_move',
        ignore_mouse_move,
        raising=False,
    )
    operation.last_screenshot = load_screen('预备编队', '已选择')

    result = operation.click_confirm()

    assert result.is_success
    assert clicked_points


@pytest.mark.parametrize(
    ('screen_name', 'state'),
    [
        ('预备编队', '未选择'),
        ('实战模拟室', '出战编队'),
    ],
)
def test_click_confirm_rejects_unavailable_text(
        test_context: FixtureTestContext,
        monkeypatch: pytest.MonkeyPatch,
        operation: ChoosePredefinedTeam,
        screen_name: str,
        state: str,
) -> None:
    """灰色禁用按钮和部分相似文字都不得让确认节点点击。"""
    def unexpected_click(
            pos: Point | None = None,
            press_time: float = 0,
            pc_alt: bool = False,
            gamepad_key: str | None = None,
    ) -> bool:
        """在不可用画面触发点击时立即让测试失败。"""
        raise AssertionError(f'不可用的预备出战不应被点击: {pos}')

    monkeypatch.setattr(test_context.controller, 'click', unexpected_click)
    operation.last_screenshot = load_screen(screen_name, state)

    result = operation.click_confirm()

    assert result.result == OperationRoundResultEnum.RETRY


def test_choose_predefined_team_runs_complete_selection_flow(
        test_context: FixtureTestContext,
        fixture_controller: FixtureController,
        predefined_team: PredefinedTeamInfo,
) -> None:
    """实际状态机必须先选中队伍，再点击白色的预备出战。"""
    fixture_controller.set_phases(
        [
            {
                'frame': ('实战模拟室', '出战编队'),
                'exit': ('on_click_in', '实战模拟室', '预备编队'),
            },
            {
                'frame': ('预备编队', '未选择'),
                'exit': ('on_click_in', list(TEAM_ONE_CARD_RECT)),
            },
            {
                'frame': ('预备编队', '已选择'),
                'exit': ('on_click_in', '实战模拟室', '预备出战'),
            },
            {'frame': ('实战模拟室', '出战编队')},
        ]
    )
    operation = _WatchedChoosePredefinedTeam(test_context, [predefined_team.idx])
    operation._init_watchdog()

    enter_running_state(test_context)
    try:
        result = operation.execute()
    finally:
        reset_running_state(test_context, operation)

    x1, y1, x2, y2 = TEAM_ONE_CARD_RECT
    assert result.success
    assert result.status == '预备出战'
    assert fixture_controller.phase_idx == 3
    assert fixture_controller.click_hit_area('实战模拟室', '预备编队')
    assert any(
        x1 <= point.x <= x2 and y1 <= point.y <= y2
        for point in fixture_controller.recorded_clicks
    )
    assert fixture_controller.click_hit_area('实战模拟室', '预备出战')
