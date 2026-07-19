import threading
import time
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunResult,
    RunFinishReason,
)
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.backend.backend_context import RunState, RunType
from zzz_od.backend.schemas import RunStatusResult


def _make_op(result=None, raises=None, node_cn='进入游戏', op_name=''):
    """构造 mock op factory;execute 阻塞到 event(若传)或立即返回 result/抛 raises。

    op_name 默认 ''(与 Operation 默认一致),使 _run 内 app fallback 到类名。
    """
    def factory(ctx):
        op = MagicMock(name='Operation')
        op.__class__ = type('OpenAndEnterGame', (), {})  # 让 __class__.__name__ == 'OpenAndEnterGame'
        op.op_name = op_name
        node = MagicMock()
        node.cn = node_cn
        op._current_node = node
        op.node_retry_times = 2
        if raises is not None:
            op.execute.side_effect = raises
        else:
            op.execute.return_value = result
        return op
    return factory


def _make_blocking_op(event, result):
    """execute 阻塞到 event.set() 的 factory(用于并发拒绝 / running 查询测试)。"""
    def factory(ctx):
        op = MagicMock(name='Operation')
        op.__class__ = type('OpenAndEnterGame', (), {})
        op.op_name = ''
        node = MagicMock()
        node.cn = '等待游戏打开'
        op._current_node = node
        op.node_retry_times = 0
        def _execute():
            event.wait(timeout=10)
            return result
        op.execute.side_effect = _execute
        return op
    return factory


# ============ op 路径:_start / _run ============

def test_start_rejects_when_running(slot):
    """单跑道:第一个运行阻塞中时,第二次 _start 必须被拒。"""
    event = threading.Event()
    slot._start('mcp', op_factory=_make_blocking_op(event, OperationResult(success=True)))
    try:
        ok, fut = slot._start('http', op_factory=_make_blocking_op(event, OperationResult(success=True)))
        assert ok is False and fut is None
    finally:
        event.set()  # 释放后台线程


def test_start_requires_exactly_one_of_op_factory_or_app_id(slot):
    """op_factory 与 app_id 必须二选一:都缺或都传 → ValueError。"""
    with pytest.raises(ValueError):
        slot._start('mcp')                                   # 都缺
    with pytest.raises(ValueError):
        slot._start('mcp', op_factory=_make_op(), app_id='x')  # 都传


def test_op_path_backfills_current_op_and_stops(slot, mock_ctx):
    """op 路径:运行中 current_op 回填、run_type=OPERATION;结束后 stop_running 被调、current_op 清除。"""
    event = threading.Event()
    _, fut = slot._start('mcp', op_factory=_make_blocking_op(event, OperationResult(success=True)))
    try:
        deadline = time.time() + 5
        while slot.current_op is None and time.time() < deadline:
            time.sleep(0.01)
        assert slot.current_op is not None                   # op 路径回填 current_op
        assert slot.run_type == RunType.OPERATION
    finally:
        event.set()
    fut.result(timeout=5)
    assert mock_ctx.run_context.stop_running.called           # op 路径 finally 调 stop_running
    assert slot.current_op is None                           # 运行结束后清除


def test_run_success(slot):
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True, status='成功打开并进入游戏')))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.SUCCESS
    assert slot.last_status == '成功打开并进入游戏'
    assert slot.app == 'OpenAndEnterGame'                     # op_name='' → fallback 类名
    assert slot.failed_node is None                           # SUCCESS 不记失败节点
    assert slot.finished_at is not None


def test_run_failed(slot):
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=False, status='打开游戏失败')))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.failed_node == '进入游戏'                      # 清 current_op 前本地捕获
    assert slot.last_status == '打开游戏失败'


def test_run_stopped(slot):
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=False, status='人工结束')))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.STOPPED
    assert slot.failed_node is None                           # STOPPED 不记失败节点


def test_run_init_failed(slot, mock_ctx):
    """start_running 返 False(有其它运行)→ FAILED,不卡 RUNNING。"""
    mock_ctx.run_context.start_running.return_value = False
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.last_status == 'start_running 失败(有其它运行)'


def test_run_exception_fixates_failed(slot):
    """op.execute 抛异常 → 顶层 except 兜住、terminal_state=FAILED,不卡 RUNNING。"""
    _, fut = slot._start('mcp', op_factory=_make_op(raises=RuntimeError('boom')))
    result = fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.last_status == '执行异常: boom'
    assert result is not None and result.success is False     # future 解析值非 None,适配器 block=True 取 .success 不崩


def test_run_syncs_current_instance_idx(slot, mock_ctx):
    """op 路径:_run 把 ctx.current_instance_idx 同步到 run_context。"""
    mock_ctx.current_instance_idx = 7
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)))
    fut.result(timeout=5)
    assert mock_ctx.run_context.current_instance_idx == 7


def test_op_path_uses_display_name_as_op_id(slot):
    """op 路径传 display_name → op_id 固化为 display_name。"""
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)),
                         display_name='zzz_od.operation.enter_game.OpenAndEnterGame')
    fut.result(timeout=5)
    assert slot.op_id == 'zzz_od.operation.enter_game.OpenAndEnterGame'


# ============ app 路径:_start(app_id) 委托 run_application ============

def test_app_path_delegates_run_application(slot, mock_ctx):
    """app 路径:run_application 被调、last_application_result 固化、app=展示名、run_type=APPLICATION。"""
    mock_ctx.run_context.run_application.return_value = ApplicationRunResult(
        finish_reason=RunFinishReason.COMPLETED,
        app_id='one_dragon', instance_idx=0, group_id='default',
    )
    mock_ctx.run_context.last_application_result = OperationResult(success=True, status='一条龙完成')
    mock_ctx.run_context.get_application_name.return_value = '一条龙'

    _, fut = slot._start('mcp', app_id='one_dragon', instance_idx=0, group_id='default',
                         refresh_config=lambda: None)
    fut.result(timeout=5)

    mock_ctx.run_context.run_application.assert_called_once()
    assert slot.terminal_state == RunState.SUCCESS
    assert slot.app == '一条龙'                               # get_application_name 固化
    assert slot.run_type == RunType.APPLICATION
    assert slot.op_id == 'one_dragon'                         # app_id 即唯一标识
    assert slot.last_status == '一条龙完成'


def test_app_path_refresh_config_called(slot, mock_ctx):
    """app 路径:refresh_config 在 run_application 前被调。"""
    mock_ctx.run_context.run_application.return_value = ApplicationRunResult(
        finish_reason=RunFinishReason.COMPLETED,
        app_id='one_dragon', instance_idx=0, group_id='default',
    )
    mock_ctx.run_context.last_application_result = OperationResult(success=True, status='ok')
    mock_ctx.run_context.get_application_name.return_value = '一条龙'
    called = []
    def refresh():
        called.append(True)
    _, fut = slot._start('mcp', app_id='one_dragon', group_id='default', refresh_config=refresh)
    fut.result(timeout=5)
    assert called == [True]


def test_refresh_config_not_called_when_rejected(slot):
    """槽在跑时第二个 _start 返 (False, None) 且 refresh_config 未被调。"""
    event = threading.Event()
    refresh_calls = []
    def refresh():
        refresh_calls.append(True)
    slot._start('mcp', op_factory=_make_blocking_op(event, OperationResult(success=True)))
    try:
        ok, fut = slot._start('mcp', app_id='one_dragon', group_id='default', refresh_config=refresh)
        assert ok is False and fut is None
        assert refresh_calls == []                            # 拒绝路径不刷新
    finally:
        event.set()


def test_app_path_init_failure_does_not_reuse_stale_result(slot, mock_ctx):
    """app 启动失败时不得把上一次应用结果误判为本次结果。"""
    mock_ctx.run_context.run_application.return_value = ApplicationRunResult(
        finish_reason=RunFinishReason.NOT_STARTED,
        app_id='one_dragon', instance_idx=0, group_id='default',
    )
    mock_ctx.run_context.last_application_result = OperationResult(
        success=True, status='上一次成功',
    )
    mock_ctx.run_context.get_application_name.return_value = '一条龙'

    _, fut = slot._start('mcp', app_id='one_dragon', group_id='default')
    fut.result(timeout=5)

    assert slot.terminal_state == RunState.FAILED
    assert slot.last_status == f'应用运行失败: {RunFinishReason.NOT_STARTED}'


def test_app_path_exception_fixates_failed(slot, mock_ctx):
    """app 路径 run_application 抛异常 → 顶层 except 兜住、terminal_state=FAILED。"""
    mock_ctx.run_context.run_application.side_effect = RuntimeError('app boom')
    mock_ctx.run_context.get_application_name.return_value = '一条龙'
    _, fut = slot._start('mcp', app_id='one_dragon', group_id='default')
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.last_status == '执行异常: app boom'


# ============ _query_status / _stop ============

def test_query_status_idle(slot):
    r = slot._query_status()
    assert isinstance(r, RunStatusResult)
    assert r.state == 'idle' and r.source is None


def test_query_status_running(slot):
    event = threading.Event()
    slot._start('mcp', op_factory=_make_blocking_op(event, OperationResult(success=True)))
    try:
        # 等后台线程进入 blocking op(设置了 current_op 后才阻塞在 event.wait)。
        deadline = time.time() + 5
        while slot.current_op is None and time.time() < deadline:
            time.sleep(0.01)
        r = slot._query_status()
        assert r.state == 'running'
        assert r.source == 'mcp'
        assert r.current_node == '等待游戏打开'
        assert r.retry_count == 0
        assert r.started_at is not None and r.duration_seconds is not None
    finally:
        event.set()


def test_query_status_terminal_failed(slot):
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=False, status='打开游戏失败')))
    fut.result(timeout=5)
    r = slot._query_status()
    assert r.state == 'failed'
    assert r.last_status == '打开游戏失败'
    assert r.failed_node == '进入游戏'
    assert r.app == 'OpenAndEnterGame'
    assert r.current_node is None


def test_stop_idle_returns_false(slot):
    """无运行时 _stop 返回 (False, None),不调 stop_running。"""
    assert slot._stop() == (False, None)


def test_stop_running_signals_stop(slot, mock_ctx):
    """运行中 _stop 读出 source、锁外调 stop_running,返回 (True, source)。"""
    event = threading.Event()
    slot._start('http', op_factory=_make_blocking_op(event, OperationResult(success=True)))
    try:
        stopped, source = slot._stop()
        assert stopped is True and source == 'http'
        assert mock_ctx.run_context.stop_running.called
        assert mock_ctx.run_context.stop_running.call_args.args == ()
    finally:
        event.set()


# ============ ZzzBackendContext 委托(单槽:start_run/query_status/stop 都走 run_slot) ============

def test_context_start_run_delegates(slot, mock_ctx):
    """ZzzBackendContext.start_run 转发 run_slot._start,返回 (ok, future)。"""
    from zzz_od.backend.backend_context import ZzzBackendContext

    backend = ZzzBackendContext(mock_ctx)
    backend.run_slot = slot
    ok, fut = backend.start_run('mcp', _make_op(OperationResult(success=True)))
    assert ok is True and fut is not None
    fut.result(timeout=5)


def test_context_start_run_rejected_when_slot_running(slot, mock_ctx):
    """单槽:run_slot 已在跑时,start_run 返 (False, None)。"""
    from zzz_od.backend.backend_context import ZzzBackendContext

    backend = ZzzBackendContext(mock_ctx)
    backend.run_slot = slot
    # 先占住单跑道(blocking op),再 start_run 应被拒。
    event = threading.Event()
    slot._start('mcp', op_factory=_make_blocking_op(event, OperationResult(success=True)))
    try:
        ok, fut = backend.start_run('mcp', _make_op(OperationResult(success=True)))
        assert ok is False and fut is None
    finally:
        event.set()  # 释放后台线程


def test_context_start_run_display_name_passthrough(slot, mock_ctx):
    """start_run 的 display_name 透传到 _start 的 op_id。"""
    from zzz_od.backend.backend_context import ZzzBackendContext

    backend = ZzzBackendContext(mock_ctx)
    backend.run_slot = slot
    _, fut = backend.start_run('mcp', _make_op(OperationResult(success=True)),
                               display_name='pkg.Cls')
    fut.result(timeout=5)
    assert slot.op_id == 'pkg.Cls'


def test_context_query_status_delegates(slot, mock_ctx):
    """ZzzBackendContext.query_status 单槽转发(idle 可达)。"""
    from zzz_od.backend.backend_context import ZzzBackendContext

    backend = ZzzBackendContext(mock_ctx)
    backend.run_slot = slot
    assert backend.query_status().state == 'idle'


def test_context_stop_delegates(slot, mock_ctx):
    """ZzzBackendContext.stop 单槽封装(无运行时返 {stopped:False, error})。"""
    from zzz_od.backend.backend_context import ZzzBackendContext

    backend = ZzzBackendContext(mock_ctx)
    backend.run_slot = slot
    assert backend.stop() == {'stopped': False, 'error': '当前无运行'}
