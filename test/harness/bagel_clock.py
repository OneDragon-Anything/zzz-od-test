"""离线操作使用的受控时钟，不修改 Python 的共享 time 模块。"""

import time as _real_time


class OperationClock:
    """真实计时加逻辑等待，保留计算耗时与业务超时。"""

    def __init__(self) -> None:
        """每个测试从零等待量开始。"""
        self.elapsed: float = 0.0

    def time(self) -> float:
        """返回与模拟截图一致的时间戳。"""
        return _real_time.time() + self.elapsed

    def monotonic(self) -> float:
        """返回包含模拟等待的单调时间。"""
        return _real_time.monotonic() + self.elapsed

    def sleep(self, seconds: float) -> None:
        """只推进业务等待，不阻塞后台事件线程。"""
        self.elapsed += max(0, seconds)
