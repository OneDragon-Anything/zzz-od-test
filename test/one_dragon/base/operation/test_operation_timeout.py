"""操作框架超时兜底测试 对应 issue #2945。

锄大地传送的「打开3D地图」round_wait 分支不受重试次数约束（WAIT 不计数），
「选择区域↔选择子区域」往返时每个节点的重试次数会被清零，
两处都只能靠节点级 / 操作级 timeout_seconds 终止。
"""
import time

import numpy as np
import pytest
from typing import Any

from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.base.operation.notify_pool import NotifyPool
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult


class FakeNotifyConfig:
    enable_notify = False


class FakeController:
    def screenshot(self):
        return time.time(), np.zeros((10, 10, 3), dtype=np.uint8)


class FakeRunContext:
    is_context_stop = False
    is_context_pause = False
    event_bus = ContextEventBus()
    notify_pool = NotifyPool()


class FakeCtx:
    run_context = FakeRunContext()
    notify_config = FakeNotifyConfig()
    event_bus = ContextEventBus()
    controller = FakeController()

    def dispatch_event(self, event_id: str, event_obj: Any = None) -> None:
        self.event_bus.dispatch_event(event_id, event_obj)

    def unlisten_all_event(self, obj: Any) -> None:
        self.event_bus.unlisten_all_event(obj)

    def listen_event(self, event_id: str, callback) -> None:
        self.event_bus.listen_event(event_id, callback)


class WaitForeverOp(Operation):
    """模拟「打开3D地图」：一直 round_wait 无重试计数 靠节点超时终止。"""

    def __init__(self):
        Operation.__init__(self, ctx=FakeCtx(), op_name='模拟-打开3D地图',
                           need_check_game_win=False)

    @operation_node(name='等待节点', is_start_node=True, timeout_seconds=1)
    def wait_node(self) -> OperationRoundResult:
        return self.round_wait(status='点击打开3D地图', wait=0)


class BounceOp(Operation):
    """模拟「选择区域↔选择子区域」往返：区域每次选上 子区域一直找不到 无限循环
    靠操作级超时终止。"""

    def __init__(self):
        Operation.__init__(self, ctx=FakeCtx(), op_name='模拟-选择区域往返',
                           timeout_seconds=1, need_check_game_win=False)

    @operation_node(name='节点A-选择区域', is_start_node=True)
    def node_a(self) -> OperationRoundResult:
        return self.round_success(wait=0)

    @node_from(from_name='节点A-选择区域')
    @node_from(from_name='节点B-选择子区域', success=False)
    @operation_node(name='节点B-选择子区域')
    def node_b(self) -> OperationRoundResult:
        return self.round_fail(status='找不到子区域')


class NormalWaitOp(Operation):
    """正常场景：round_retry 若干轮后成功 不应被超时误伤。"""

    def __init__(self):
        Operation.__init__(self, ctx=FakeCtx(), op_name='模拟-正常等待',
                           need_check_game_win=False)

    @operation_node(name='等待节点', is_start_node=True, timeout_seconds=10)
    def wait_node(self) -> OperationRoundResult:
        if self.node_retry_times >= 2:
            return self.round_success()
        return self.round_retry(status='重试中', wait=0)


def test_wait_loop_terminated_by_node_timeout():
    start = time.time()
    result = WaitForeverOp().execute()
    elapsed = time.time() - start

    assert not result.success
    assert result.status == '执行超时'
    assert elapsed < 10


def test_node_bounce_terminated_by_operation_timeout():
    start = time.time()
    result = BounceOp().execute()
    elapsed = time.time() - start

    assert not result.success
    assert result.status == '执行超时'
    assert elapsed < 10


def test_normal_retry_not_affected():
    result = NormalWaitOp().execute()

    assert result.success
