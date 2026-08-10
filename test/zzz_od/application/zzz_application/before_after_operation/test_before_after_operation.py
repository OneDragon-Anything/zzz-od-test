from unittest.mock import MagicMock, patch

from one_dragon.base.operation.application_base import ApplicationEventId
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class _TestApplication(ZApplication):

    business_success: bool = True
    business_status: str = '业务完成'
    next_node_executed: bool = False
    execution_order: list[str] | None = None

    @operation_node(name='业务节点', screenshot_before_round=False)
    def business_node(self) -> OperationRoundResult:
        if self.execution_order is not None:
            self.execution_order.append('业务')
        if self.business_success:
            return self.round_success(self.business_status)
        return self.round_fail(self.business_status)

    @node_from(from_name='业务节点', status='继续')
    @operation_node(name='后续业务节点', screenshot_before_round=False)
    def next_business_node(self) -> OperationRoundResult:
        self.next_node_executed = True
        return self.round_success('后续业务完成')


def _make_ctx() -> ZContext:
    ctx: ZContext = MagicMock()
    ctx.run_context.is_context_stop = False
    ctx.run_context.is_context_pause = False
    ctx.run_context.is_app_need_notify.return_value = False
    ctx.notify_config.enable_notify = False
    return ctx


def _make_app(ctx: ZContext | None = None) -> _TestApplication:
    return _TestApplication(
        ctx=_make_ctx() if ctx is None else ctx,
        app_id='test_app',
        need_check_game_win=False,
        run_record=MagicMock(),
    )


def _make_app_with_operations(
    op_before: Operation | None = None,
    op_after: Operation | None = None,
    ctx: ZContext | None = None,
    need_check_game_win: bool = False,
) -> _TestApplication:
    return _TestApplication(
        ctx=_make_ctx() if ctx is None else ctx,
        app_id='test_app',
        need_check_game_win=need_check_game_win,
        run_record=MagicMock(),
        op_before=op_before,
        op_after=op_after,
    )


def test_success_runs_default_after_operation() -> None:
    with patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls:
        back_cls.return_value.execute.return_value = Operation.op_success('大世界-普通')
        app = _make_app()

        back_cls.assert_called_once_with(app.ctx)
        back_cls.return_value.execute.assert_not_called()

        first_result = app.execute()
        second_result = app.execute()

    assert back_cls.return_value.execute.call_count == 2
    assert first_result.success
    assert first_result.status == '大世界-普通'
    assert second_result.success
    assert second_result.status == '大世界-普通'


def test_after_operation_failure_changes_final_result() -> None:
    with patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls:
        back_cls.return_value.execute.return_value = Operation.op_fail('未能识别当前画面')
        app = _make_app()
        result = app.execute()

    back_cls.assert_called_once_with(app.ctx)
    back_cls.return_value.execute.assert_called_once_with()
    assert not result.success
    assert result.status == '未能识别当前画面'


def test_after_operation_exception_still_finishes_application() -> None:
    ctx = _make_ctx()
    after_operation = MagicMock(spec=Operation)
    after_operation.execute.side_effect = RuntimeError('后置操作异常')
    app = _make_app_with_operations(
        op_after=after_operation,
        ctx=ctx,
    )

    result = app.execute()

    assert after_operation.execute.called
    assert not result.success
    assert result.status == '异常'
    assert app.run_record is not None
    app.run_record.update_status.assert_any_call(AppRunRecord.STATUS_FAIL)
    ctx.dispatch_event.assert_any_call(
        ApplicationEventId.APPLICATION_STOP.value,
        app.app_id,
    )


def test_business_failure_does_not_run_after_operation() -> None:
    with patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls:
        app = _make_app()
        app.business_success = False
        app.business_status = '业务失败'
        result = app.execute()

    back_cls.assert_called_once_with(app.ctx)
    back_cls.return_value.execute.assert_not_called()
    assert not result.success
    assert result.status == '业务失败'


def test_timeout_does_not_run_after_operation() -> None:
    with patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls:
        app = _TestApplication(
            ctx=_make_ctx(),
            app_id='test_app',
            timeout_seconds=0,
            need_check_game_win=False,
            run_record=MagicMock(),
        )
        result = app.execute()

    back_cls.return_value.execute.assert_not_called()
    assert not result.success
    assert result.status == Operation.STATUS_TIMEOUT


def test_manual_stop_does_not_run_after_operation() -> None:
    ctx = _make_ctx()
    ctx.run_context.is_context_stop = True

    with patch('zzz_od.application.zzz_application.BackToNormalWorld') as back_cls:
        app = _make_app(ctx)
        result = app.execute()

    back_cls.return_value.execute.assert_not_called()
    assert not result.success
    assert result.status == '人工结束'


def test_disabled_after_operation_does_not_return_to_world() -> None:
    app = _make_app_with_operations()
    result = app.execute()

    assert result.success
    assert result.status == '业务完成'


def test_before_and_after_operations_are_attached_during_initialization() -> None:
    ctx = _make_ctx()
    execution_order: list[str] = []
    before_operation = MagicMock(spec=Operation)
    before_operation.execute.side_effect = lambda: (
        execution_order.append('前置') or Operation.op_success('前置完成')
    )
    after_operation = MagicMock(spec=Operation)
    after_operation.execute.side_effect = lambda: (
        execution_order.append('后置') or Operation.op_success('后置完成')
    )

    app = _make_app_with_operations(before_operation, after_operation, ctx)
    app.execution_order = execution_order

    assert app._before_node is not None
    assert app._before_node.op is before_operation
    assert app._after_node is not None
    assert app._after_node.op is after_operation
    before_operation.execute.assert_not_called()
    after_operation.execute.assert_not_called()

    result = app.execute()

    assert execution_order == ['前置', '业务', '后置']
    assert result.success
    assert result.status == '后置完成'


def test_before_operation_failure_stops_business_and_after_operation() -> None:
    execution_order: list[str] = []
    before_operation = MagicMock(spec=Operation)
    before_operation.execute.side_effect = lambda: (
        execution_order.append('前置') or Operation.op_fail('前置失败')
    )
    after_operation = MagicMock(spec=Operation)
    after_operation.execute.return_value = Operation.op_success('后置完成')
    app = _make_app_with_operations(
        op_before=before_operation,
        op_after=after_operation,
    )
    app.execution_order = execution_order

    result = app.execute()

    assert execution_order == ['前置']
    after_operation.execute.assert_not_called()
    assert not result.success
    assert result.status == '前置失败'


def test_existing_success_edge_runs_before_after_operation() -> None:
    after_operation = MagicMock(spec=Operation)
    after_operation.execute.return_value = Operation.op_success('后置完成')
    app = _make_app_with_operations(
        op_after=after_operation,
    )
    app.business_status = '继续'

    result = app.execute()

    assert app.next_node_executed
    after_operation.execute.assert_called_once_with()
    assert result.success
    assert result.status == '后置完成'


def test_unmatched_success_status_uses_after_operation_fallback_edge() -> None:
    after_operation = MagicMock(spec=Operation)
    after_operation.execute.return_value = Operation.op_success('后置完成')
    app = _make_app_with_operations(
        op_after=after_operation,
    )
    app.business_status = '提前完成'

    result = app.execute()

    assert not app.next_node_executed
    after_operation.execute.assert_called_once_with()
    assert result.success
    assert result.status == '后置完成'
