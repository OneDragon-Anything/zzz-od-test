from pathlib import Path
from typing import Any

import pytest
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import cv2_utils
from zzz_od.config.team_config import PredefinedTeamInfo, TeamConfig
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam

SCREEN_ROOT = Path(__file__).resolve().parents[4] / 'screens'


def load_screen(screen_name: str, state: str) -> MatLike:
    image = cv2_utils.read_image(str(SCREEN_ROOT / screen_name / f'{state}.webp'))
    assert image is not None
    return image


@pytest.fixture
def predefined_team(monkeypatch: pytest.MonkeyPatch) -> PredefinedTeamInfo:
    team = PredefinedTeamInfo(idx=0, name='编队1', auto_battle='全配队通用', agent_id_list=[])

    def get_team_list(_config: TeamConfig) -> list[PredefinedTeamInfo]:
        return [team]

    monkeypatch.setattr(TeamConfig, 'team_list', property(get_team_list))
    return team


def test_click_team_waits_until_entry_disappears(
        test_context: Any,
        predefined_team: PredefinedTeamInfo,
) -> None:
    op = ChoosePredefinedTeam(test_context, [predefined_team.idx])

    test_context.add_mock_screenshot(load_screen('实战模拟室', '出战编队'))
    op.screenshot()
    first_result = op.click_team()

    assert first_result.result == OperationRoundResultEnum.WAIT
    assert first_result.status == '预备编队'

    test_context.add_mock_screenshot(load_screen('预备编队', '未选择'))
    op.screenshot()
    second_result = op.click_team()

    assert second_result.is_success
    assert second_result.status == '预备编队'


def test_choose_team_clicks_target_when_confirm_is_disabled(
        test_context: Any,
        monkeypatch: pytest.MonkeyPatch,
        predefined_team: PredefinedTeamInfo,
) -> None:
    clicked_points: list[Point] = []

    def record_click(
            pos: Point | None = None,
            press_time: float = 0,
            pc_alt: bool = False,
            gamepad_key: str | None = None,
    ) -> bool:
        if pos is not None:
            clicked_points.append(pos)
        return True

    monkeypatch.setattr(test_context.controller, 'click', record_click)
    test_context.add_mock_screenshot(load_screen('预备编队', '未选择'))
    op = ChoosePredefinedTeam(test_context, [predefined_team.idx])
    op.screenshot()

    result = op.choose_team()

    assert result.result == OperationRoundResultEnum.WAIT
    assert clicked_points


def test_choose_team_accepts_enabled_confirm(
        test_context: Any,
        predefined_team: PredefinedTeamInfo,
) -> None:
    test_context.add_mock_screenshot(load_screen('预备编队', '已选择'))
    op = ChoosePredefinedTeam(test_context, [predefined_team.idx])
    op.screenshot()

    result = op.choose_team()

    assert result.is_success
    assert result.status == '预备出战'


def test_click_confirm_rejects_disabled_button(
        test_context: Any,
        monkeypatch: pytest.MonkeyPatch,
        predefined_team: PredefinedTeamInfo,
) -> None:
    def unexpected_click(
            pos: Point | None = None,
            press_time: float = 0,
            pc_alt: bool = False,
            gamepad_key: str | None = None,
    ) -> bool:
        raise AssertionError(f'禁用按钮不应被点击: {pos}')

    monkeypatch.setattr(test_context.controller, 'click', unexpected_click)
    test_context.add_mock_screenshot(load_screen('预备编队', '未选择'))
    op = ChoosePredefinedTeam(test_context, [predefined_team.idx])
    op.screenshot()

    result = op.click_confirm()

    assert result.result == OperationRoundResultEnum.RETRY


def test_choose_team_requires_full_confirm_text(
        test_context: Any,
        monkeypatch: pytest.MonkeyPatch,
        predefined_team: PredefinedTeamInfo,
) -> None:
    thresholds: list[float] = []
    op = ChoosePredefinedTeam(test_context, [predefined_team.idx])

    def fake_round_by_ocr(
            screen: MatLike,
            target_cn: str,
            area: ScreenArea | None = None,
            lcs_percent: float = 0.5,
            success_wait: float | None = None,
            success_wait_round: float | None = None,
            retry_wait: float | None = None,
            retry_wait_round: float | None = None,
            color_range: list[list[int]] | None = None,
    ) -> OperationRoundResult:
        thresholds.append(lcs_percent)
        if lcs_percent < 1:
            return op.round_success(target_cn)
        return op.round_retry(f'找不到 {target_cn}')

    def empty_ocr(_screen: MatLike) -> dict[str, MatchResultList]:
        return {}

    monkeypatch.setattr(op, 'round_by_ocr', fake_round_by_ocr)
    monkeypatch.setattr(test_context.ocr, 'run_ocr', empty_ocr)
    op.last_screenshot = load_screen('实战模拟室', '出战编队')

    result = op.choose_team()

    assert thresholds == [1.0]
    assert not result.is_success
    assert result.status == '当前页未找到编队 编队1'
