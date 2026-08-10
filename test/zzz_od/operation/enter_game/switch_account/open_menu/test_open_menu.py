from unittest.mock import MagicMock, patch

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.operation.enter_game.switch_account import SwitchAccount


def _make_operation() -> SwitchAccount:
    ctx = MagicMock()
    ctx.game_account_config.has_login_info = True
    return SwitchAccount(ctx)


def test_open_menu_uses_goto_menu_and_propagates_success() -> None:
    op = _make_operation()
    expected_data = {'screen': '菜单'}

    with patch('zzz_od.operation.enter_game.switch_account.GotoMenu') as goto_menu_cls:
        goto_menu_cls.return_value.execute.return_value = OperationResult(
            success=True,
            status='菜单',
            data=expected_data,
        )
        result = op.open_menu()

    goto_menu_cls.assert_called_once_with(op.ctx)
    goto_menu_cls.return_value.execute.assert_called_once_with()
    assert result.is_success
    assert result.status == '菜单'
    assert result.data is expected_data


def test_open_menu_uses_goto_menu_and_propagates_failure() -> None:
    op = _make_operation()
    expected_data = {'screen': '未知'}

    with patch('zzz_od.operation.enter_game.switch_account.GotoMenu') as goto_menu_cls:
        goto_menu_cls.return_value.execute.return_value = OperationResult(
            success=False,
            status='返回大世界失败',
            data=expected_data,
        )
        result = op.open_menu()

    goto_menu_cls.assert_called_once_with(op.ctx)
    goto_menu_cls.return_value.execute.assert_called_once_with()
    assert result.is_fail
    assert result.status == '返回大世界失败'
    assert result.data is expected_data
