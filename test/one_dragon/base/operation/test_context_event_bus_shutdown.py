from concurrent.futures import ThreadPoolExecutor

from one_dragon.base.operation import context_event_bus
from one_dragon.base.operation.context_event_bus import ContextEventBus


def test_dispatch_event_normal():
    """正常状态下事件派发到监听者。"""
    called = []
    bus = ContextEventBus()
    bus.listen_event('TEST_EVENT', lambda item: called.append(item.data))
    bus.dispatch_event('TEST_EVENT', 'hello')

    import time
    for _ in range(50):
        if called:
            break
        time.sleep(0.1)

    assert called == ['hello']


def test_dispatch_event_after_executor_shutdown(monkeypatch):
    """事件总线线程池关闭后 派发事件降级为日志 不抛 RuntimeError。

    对应 issue #2844：运行中关闭应用时 run_context 清理向已关闭的
    事件总线派发停止事件，修复前会抛 cannot schedule new futures after shutdown。
    """
    called = []
    bus = ContextEventBus()
    bus.listen_event('TEST_EVENT', lambda item: called.append(item.data))

    # 用独立的 executor 模拟已关闭状态 不污染模块级全局线程池
    test_executor = ThreadPoolExecutor(thread_name_prefix='test_event_bus')
    monkeypatch.setattr(context_event_bus, '_od_event_bus_executor', test_executor)
    test_executor.shutdown(wait=False, cancel_futures=True)

    # 修复前这里抛 RuntimeError
    bus.dispatch_event('TEST_EVENT', 'after-shutdown')

    assert bus.has_event_listener('TEST_EVENT')
    assert called == []
