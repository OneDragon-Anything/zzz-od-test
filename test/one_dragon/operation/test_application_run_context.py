from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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


def test_registry_derives_default_and_standalone_lists() -> None:
    """三个合法入口组合应派生出不同的通用列表。"""
    rc = ApplicationRunContext(MagicMock())
    default_factory = SimpleNamespace(
        app_id='default_app',
        default_group=True,
        internal_app=False,
    )
    standalone_factory = SimpleNamespace(
        app_id='standalone_app',
        default_group=False,
        internal_app=False,
    )
    internal_factory = SimpleNamespace(
        app_id='internal_app',
        default_group=False,
        internal_app=True,
    )

    rc.registry_application([
        default_factory,
        standalone_factory,
        internal_factory,
    ])

    assert rc.default_group_apps == ['default_app']
    assert rc.standalone_apps == ['default_app', 'standalone_app']
    assert rc.is_app_registered('internal_app')
    assert rc.is_app_internal('internal_app')
    assert not rc.is_app_standalone_available('internal_app')
    assert rc.is_app_standalone_available('standalone_app')
    assert not rc.is_app_internal('missing_app')

    rc.clear_applications()
    rc.registry_application(standalone_factory)

    assert rc.default_group_apps == []
    assert rc.standalone_apps == ['standalone_app']
    assert not rc.is_app_registered('internal_app')


def test_run_application_still_allows_internal_app() -> None:
    """internal 只限制通用入口，底层运行接口仍能执行。"""
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller.init_before_context_run.return_value = True
    rc = ApplicationRunContext(ctx)
    app = MagicMock()
    app.execute.return_value = OperationResult(success=True, status='完成')
    internal_factory = SimpleNamespace(
        app_id='internal_app',
        app_name='内部应用',
        default_group=False,
        internal_app=True,
        need_notify=False,
        create_application=MagicMock(return_value=app),
    )
    rc.registry_application(internal_factory)

    result = rc.run_application('internal_app', 0, 'default')

    assert result.finish_reason == RunFinishReason.COMPLETED
    app.execute.assert_called_once_with()


def test_check_all_run_records_propagates_creation_error() -> None:
    """运行记录刷新错误不能再被当成“无记录”静默跳过。"""
    rc = ApplicationRunContext(MagicMock())
    factory = MagicMock()
    factory.get_run_record.side_effect = RuntimeError('record broken')
    rc._application_factory_map = {'broken_app': factory}

    with pytest.raises(RuntimeError, match='record broken'):
        rc.check_and_update_all_run_record(instance_idx=1)
