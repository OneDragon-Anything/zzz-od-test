from unittest.mock import MagicMock, patch

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.zzz_application import ZApplication


def _make_app(return_to_world_after_success: bool = True) -> ZApplication:
    return ZApplication(
        ctx=MagicMock(),
        app_id='test_app',
        op_to_enter_game=MagicMock(),
        run_record=MagicMock(),
        return_to_world_after_success=return_to_world_after_success,
    )


def test_success_returns_to_world() -> None:
    app = _make_app()
    result = OperationResult(success=True, status='业务完成')

    with (
        patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls,
        patch.object(Application, 'after_operation_done') as parent_after_done,
    ):
        back_cls.return_value.execute.return_value = OperationResult(
            success=True,
            status='大世界-普通',
        )
        app.after_operation_done(result)

    back_cls.assert_called_once_with(app.ctx)
    back_cls.return_value.execute.assert_called_once_with()
    parent_after_done.assert_called_once_with(app, result)
    assert result.success
    assert result.status == '业务完成'


def test_return_to_world_failure_changes_final_result() -> None:
    app = _make_app()
    result = OperationResult(success=True, status='业务完成')

    with (
        patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls,
        patch.object(Application, 'after_operation_done') as parent_after_done,
    ):
        back_cls.return_value.execute.return_value = OperationResult(
            success=False,
            status='未能识别当前画面',
        )
        app.after_operation_done(result)

    parent_after_done.assert_called_once_with(app, result)
    assert not result.success
    assert result.status == '返回大世界失败: 未能识别当前画面'


def test_business_failure_does_not_return_to_world() -> None:
    app = _make_app()
    result = OperationResult(success=False, status='业务失败')

    with (
        patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls,
        patch.object(Application, 'after_operation_done') as parent_after_done,
    ):
        app.after_operation_done(result)

    back_cls.assert_not_called()
    parent_after_done.assert_called_once_with(app, result)
    assert not result.success
    assert result.status == '业务失败'


def test_disabled_default_cleanup_does_not_return_to_world() -> None:
    app = _make_app(return_to_world_after_success=False)
    result = OperationResult(success=True, status='业务完成')

    with (
        patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls,
        patch.object(Application, 'after_operation_done') as parent_after_done,
    ):
        app.after_operation_done(result)

    back_cls.assert_not_called()
    parent_after_done.assert_called_once_with(app, result)
    assert result.success
    assert result.status == '业务完成'
