from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from zzz_od.config.team_config import PredefinedTeamInfo, TeamConfig
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam


def _make_match_result_list(x: int, y: int, w: int, h: int) -> MatchResultList:
    result_list = MatchResultList()
    result_list.append(MatchResult(0.9, x, y, w, h))
    return result_list


def test_predefined_team_info_removes_all_name_whitespace() -> None:
    """配置读取时移除半角、全角和制表符空白。"""
    team = PredefinedTeamInfo(0, '新 队　伍\t一', '全配队通用', [])
    assert team.name == '新队伍一'



def test_update_team_removes_name_whitespace_before_save() -> None:
    """前端修改后的原始名称在写入 YAML 前移除全部空白。"""
    config = object.__new__(TeamConfig)
    team = PredefinedTeamInfo(0, '旧队伍', '全配队通用', [])
    team.name = '新 队　伍\t三'
    with (
        patch.object(
            TeamConfig,
            'team_list',
            new_callable=PropertyMock,
            return_value=[team],
        ),
        patch.object(TeamConfig, 'update') as update,
    ):
        config.update_team(team)

    assert team.name == '新队伍三'
    update.assert_called_once_with(
        'team_list',
        [
            {
                'name': '新队伍三',
                'auto_battle': '全配队通用',
                'agent_id_list': ['unknown', 'unknown', 'unknown'],
            }
        ],
    )


def test_update_team_name_by_idx_removes_whitespace() -> None:
    """按序号同步名称时，保存前移除 OCR 结果中的空白。"""
    config = object.__new__(TeamConfig)
    team = PredefinedTeamInfo(2, '旧队伍', '全配队通用', [])
    with (
        patch.object(TeamConfig, 'get_team_by_idx', return_value=team),
        patch.object(TeamConfig, 'update_team') as update_team,
    ):
        config.update_team_name_by_idx(2, '新 队　伍\t二')

    assert team.name == '新队伍二'
    update_team.assert_called_once_with(team)


@pytest.mark.parametrize(
    ('team_idx', 'expected_rect'),
    [
        (0, Rect(150, 115, 450, 185)),
        (3, Rect(970, 398, 1270, 468)),
        (4, Rect(150, 115, 450, 185)),
        (7, Rect(970, 398, 1270, 468)),
    ],
)
def test_get_team_name_rect_by_idx(team_idx: int, expected_rect: Rect) -> None:
    """每页按四个新卡位定位，底部重叠卡片不作为选择目标。"""
    assert ChoosePredefinedTeam._get_team_name_rect_by_idx(team_idx) == expected_rect


def test_choose_team_uses_team_idx_card_and_updates_name() -> None:
    """本地名称过期时，按 team_idx 卡位识别新名称、更新配置并点击该卡。"""
    ctx = MagicMock()
    team = PredefinedTeamInfo(5, '旧队伍', '全配队通用', [])
    ctx.team_config.get_team_by_idx.return_value = team
    ctx.ocr.run_ocr.return_value = {
        '新 队伍': _make_match_result_list(970, 115, 100, 30),
        'SELECT': _make_match_result_list(1600, 245, 100, 20),
    }
    op = ChoosePredefinedTeam(ctx, target_team_idx_list=[5], start_at_team_list=True)
    op.current_scroll_page = 1
    op.last_screenshot = MagicMock()

    with patch('zzz_od.operation.choose_predefined_team.time.sleep'):
        result = op.choose_team()

    assert result.status == ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE
    ctx.team_config.update_team_name_by_idx.assert_called_once_with(5, '新队伍')
    clicked_point = ctx.controller.click.call_args.args[0]
    assert clicked_point.tuple() == (1320, 130)
    assert op.pending_select_button_center.tuple() == (1650, 255)
