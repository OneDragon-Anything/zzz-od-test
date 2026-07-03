import threading
import time
from unittest.mock import MagicMock

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.backend.backend_context import RunState
from zzz_od.backend.schemas import RunStatusResult


def _make_op(result=None, raises=None, node_cn='进入游戏'):
    """构造 mock op factory;execute 阻塞到 event(若传)或立即返回 result/抛 raises。"""
    def factory(ctx):
        op = MagicMock(name='Operation')
        op.__class__ = type('OpenAndEnterGame', (), {})  # 让 __class__.__name__ == 'OpenAndEnterGame'
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


def test_start_run_rejects_when_running(slot):
    """单跑道:第一个运行阻塞中时,第二次 _start_run 必须被拒。"""
    event = threading.Event()
    slot._start_run('mcp', _make_blocking_op(event, OperationResult(success=True)))
    try:
        ok, fut = slot._start_run('http', _make_blocking_op(event, OperationResult(success=True)))
        assert ok is False and fut is None
    finally:
        event.set()  # 释放后台线程


def test_run_success(slot):
    _, fut = slot._start_run('mcp', _make_op(OperationResult(success=True, status='成功打开并进入游戏')))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.SUCCESS
    assert slot.last_status == '成功打开并进入游戏'
    assert slot.app == 'OpenAndEnterGame'
    assert slot.finished_at is not None


def test_run_failed(slot):
    _, fut = slot._start_run('mcp', _make_op(OperationResult(success=False, status='打开游戏失败')))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.failed_node == '进入游戏'
    assert slot.last_status == '打开游戏失败'


def test_run_stopped(slot):
    _, fut = slot._start_run('mcp', _make_op(OperationResult(success=False, status='人工结束')))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.STOPPED


def test_run_init_failed(slot, mock_ctx):
    mock_ctx.run_context.start_running.return_value = False
    _, fut = slot._start_run('mcp', _make_op(OperationResult(success=True)))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.failed_node == 'start_running 初始化失败'


def test_run_exception(slot):
    _, fut = slot._start_run('mcp', _make_op(raises=RuntimeError('boom')))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.last_status == '执行异常'


def test_run_syncs_current_instance_idx(slot, mock_ctx):
    mock_ctx.current_instance_idx = 7
    _, fut = slot._start_run('mcp', _make_op(OperationResult(success=True)))
    fut.result(timeout=5)
    assert mock_ctx.run_context.current_instance_idx == 7


def test_query_status_idle(slot):
    r = slot._query_status()
    assert isinstance(r, RunStatusResult)
    assert r.state == 'idle' and r.source is None


def test_query_status_running(slot):
    event = threading.Event()
    slot._start_run('mcp', _make_blocking_op(event, OperationResult(success=True)))
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
    _, fut = slot._start_run('mcp', _make_op(OperationResult(success=False, status='打开游戏失败')))
    fut.result(timeout=5)
    r = slot._query_status()
    assert r.state == 'failed'
    assert r.last_status == '打开游戏失败'
    assert r.failed_node == '进入游戏'
    assert r.app == 'OpenAndEnterGame'
    assert r.current_node is None
