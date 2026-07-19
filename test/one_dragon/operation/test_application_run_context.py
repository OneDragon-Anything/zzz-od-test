from unittest.mock import MagicMock

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
    ApplicationRunContextStateEnum,
    RunFinishReason,
)
from one_dragon.base.operation.operation_base import OperationResult


def test_run_application_exception_writes_failed_result() -> None:
    """异常路径应写入失败的 OperationResult，而不是留 None 被误判为成功。

    覆盖 run_application 中 app.execute() 抛异常的场景：
    修复前 last_application_result 保持初始 None；修复后应写入 success=False。
    """
    ctx = MagicMock()
    ctx.ready_for_application = True
    rc = ApplicationRunContext(ctx)
    rc.register_application = lambda: None  # type: ignore[assignment]
    # 注册一个 execute 抛异常的假 app
    failing_app = MagicMock()
    failing_app.execute.side_effect = RuntimeError('boom')
    rc._application_factory_map = {
        'failing': MagicMock(
            create_application=MagicMock(return_value=failing_app),
            app_name='失败应用',
        )
    }
    rc.is_app_registered = lambda app_id: True  # type: ignore[assignment]
    rc.get_application = lambda app_id, i, g: failing_app  # type: ignore[assignment]
    rc.start_running = lambda: True  # type: ignore[assignment]
    rc.stop_running = lambda: None  # type: ignore[assignment]

    result = rc.run_application('failing', 0, 'default')

    assert result.finish_reason == RunFinishReason.FAILED
    assert rc.last_application_result is not None
    assert rc.last_application_result.success is False  # 关键：异常不再留 None
    assert isinstance(rc.last_application_result, OperationResult)
    assert 'boom' in (rc.last_application_result.status or '')


def test_run_application_result_failure_is_failed() -> None:
    """应用正常返回失败结果时，也不能被视为自然完成。"""
    ctx = MagicMock()
    ctx.ready_for_application = True
    rc = ApplicationRunContext(ctx)
    failed_app = MagicMock()
    failed_app.execute.return_value = OperationResult(success=False, status='执行失败')
    rc._application_factory_map = {'failed': MagicMock()}
    rc.is_app_registered = lambda app_id: True  # type: ignore[assignment]
    rc.get_application = lambda app_id, i, g: failed_app  # type: ignore[assignment]
    rc.start_running = lambda: True  # type: ignore[assignment]

    result = rc.run_application('failed', 0, 'default')

    assert result.finish_reason == RunFinishReason.FAILED
    assert rc.last_application_result.success is False


    """启动失败时不得收口并停止已经存在的运行。"""
    ctx = MagicMock()
    ctx.ready_for_application = True
    rc = ApplicationRunContext(ctx)
    rc._application_factory_map = {'new_app': MagicMock()}
    rc._run_state = ApplicationRunContextStateEnum.RUNNING
    rc.current_app_id = 'existing_app'
    rc.current_instance_idx = 1
    rc.current_group_id = 'existing_group'
    previous_application_result = OperationResult(success=True, status='上一次结果')
    rc.last_application_result = previous_application_result

    result = rc.run_application('new_app', 0, 'default')

    assert result.finish_reason == RunFinishReason.NOT_STARTED
    assert rc.is_context_running
    assert rc.current_app_id == 'existing_app'
    assert rc.current_instance_idx == 1
    assert rc.current_group_id == 'existing_group'
    assert rc.last_application_result is previous_application_result


def test_stop_running_is_idempotent() -> None:
    """重复停止应返回首次结果，不重复收口。"""
    ctx = MagicMock()
    rc = ApplicationRunContext(ctx)
    rc._run_state = ApplicationRunContextStateEnum.RUNNING

    first = rc.stop_running()
    second = rc.stop_running()

    assert second is first
    assert second.finish_reason == RunFinishReason.STOPPED
    assert rc.is_context_stop
