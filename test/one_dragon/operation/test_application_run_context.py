from unittest.mock import MagicMock

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
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

    started = rc.run_application('failing', 0, 'default')

    assert started is True  # 启动成功语义不变
    assert rc.last_application_result is not None
    assert rc.last_application_result.success is False  # 关键：异常不再留 None
    assert isinstance(rc.last_application_result, OperationResult)
    assert 'boom' in (rc.last_application_result.status or '')
