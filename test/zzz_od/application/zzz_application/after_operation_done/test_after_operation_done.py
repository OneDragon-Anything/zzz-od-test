from unittest.mock import MagicMock, patch

import pytest

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.zzz_application import ZApplication


def _make_app() -> ZApplication:
    return ZApplication(
        ctx=MagicMock(),
        app_id='test_app',
        op_to_enter_game=MagicMock(),
        run_record=MagicMock(),
    )


def _make_app_without_after_success_operation() -> ZApplication:
    return ZApplication(
        ctx=MagicMock(),
        app_id='test_app',
        op_to_enter_game=MagicMock(),
        run_record=MagicMock(),
        after_success_operation_factory=None,
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


def test_after_success_operation_failure_changes_final_result() -> None:
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

    back_cls.assert_called_once_with(app.ctx)
    back_cls.return_value.execute.assert_called_once_with()
    parent_after_done.assert_called_once_with(app, result)
    assert not result.success
    assert result.status == '成功后操作失败: 未能识别当前画面'


@pytest.mark.parametrize('status', ['业务失败', '执行超时', '人工结束'])
def test_unsuccessful_result_does_not_run_after_success_operation(status: str) -> None:
    app = _make_app()
    result = OperationResult(success=False, status=status)

    with (
        patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls,
        patch.object(Application, 'after_operation_done') as parent_after_done,
    ):
        app.after_operation_done(result)

    back_cls.assert_not_called()
    parent_after_done.assert_called_once_with(app, result)
    assert not result.success
    assert result.status == status


def test_disabled_after_success_operation_does_not_return_to_world() -> None:
    app = _make_app_without_after_success_operation()
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


def test_custom_after_success_operation_factory_is_used() -> None:
    ctx = MagicMock()
    after_operation = MagicMock()
    after_operation.execute.return_value = OperationResult(success=True, status='后置操作完成')
    operation_factory = MagicMock(return_value=after_operation)
    app = ZApplication(
        ctx=ctx,
        app_id='test_app',
        op_to_enter_game=MagicMock(),
        run_record=MagicMock(),
        after_success_operation_factory=operation_factory,
    )
    result = OperationResult(success=True, status='业务完成')

    with patch.object(Application, 'after_operation_done') as parent_after_done:
        app.after_operation_done(result)

    operation_factory.assert_called_once_with(ctx)
    after_operation.execute.assert_called_once_with()
    parent_after_done.assert_called_once_with(app, result)
    assert result.success
    assert result.status == '业务完成'
