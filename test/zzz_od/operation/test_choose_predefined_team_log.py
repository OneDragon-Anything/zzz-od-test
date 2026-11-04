from unittest.mock import MagicMock, patch

from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam


def test_team_disabled_details_are_logged_at_debug_level() -> None:
    """禁用判定的槽位和头像细节只在 DEBUG 级别输出。"""
    operation = ChoosePredefinedTeam.__new__(ChoosePredefinedTeam)
    agent_scan_result_list = [
        MagicMock(is_dim=False),
        MagicMock(is_dim=True),
        MagicMock(is_dim=False),
    ]

    with patch('zzz_od.operation.choose_predefined_team.log') as log:
        assert operation._is_team_disabled(
            '编队1',
            {'1P', '3P'},
            3,
            agent_scan_result_list,
        )

    log.debug.assert_called_once()
    log.info.assert_not_called()
