from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
)

from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.fixture_controller import FixtureController

    from one_dragon.base.operation.operation_round_result import OperationRoundResult


class WatchedEnter(WatchdogOperationMixin, BagelEnter):
    """保留正式节点图，并记录节点首次执行时的点击标记。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx: TestContext) -> None:
        """仅增加测试观察，不替换导航、识别或转存子操作。"""
        super().__init__(ctx, allow_clear_loadout=True)
        self.visited: list[tuple[str, bool]] = []

    def _execute_one_round(self) -> OperationRoundResult:
        """记录真实流转，避免直接调用节点漏掉路由或状态重置。"""
        name = self._current_node.cn
        if not self.visited or self.visited[-1][0] != name:
            self.visited.append((name, self.node_clicked))
        return super()._execute_one_round()


def test_starting_warehouse_returns_through_map_and_entry(
    test_context: TestContext, controller: FixtureController,
) -> None:
    """从非空仓库启动，完整执行转存、返回、重新选图及零携带零投资核验。"""
    # 各阶段使用独立存档画面，仅证明流程与输入顺序，不代替连续实机录像。
    controller.set_phases([
        {'frame': ('贝果-仓库', 'clear_carried_six_before'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', 'clear_loadout_prepare_warehouse_empty'),
         'exit': ('on_click_in', '菜单', '返回')},
        {'frame': ('贝果-备战', 'clear_loadout_empty'), 'exit': ('on_click_in', '菜单', '返回')},
        {'frame': ('贝果-选图', '城郊高危-20260926'), 'exit': ('on_click_in', '贝果-选图', '雅努斯')},
        {'frame': ('贝果-选图', '雅努斯困难-原生1080'), 'exit': ('on_click_in', '贝果-选图', '高危')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'), 'exit': ('on_click_in', '贝果-选图', '前往备战')},
        {'frame': ('贝果-备战', 'clear_loadout_empty'), 'exit': ('on_click_in', '贝果-备战', '前往空洞')},
        {'frame': ('贝果-入场确认', '高危零装备价值-原生1080'), 'exit': ('on_click_in', '贝果-入场确认', '确认')},
        {'frame': ('贝果-入场确认', '未装备武备-原生1080'), 'exit': ('on_click_in', '贝果-入场确认', '确认')},
        {'frame': ('贝果-入场确认', '未穿戴队伍装备-原生1080'), 'exit': ('on_click_in', '贝果-入场确认', '确认')},
        {'frame': ('贝果-入场确认', '高危零投资-原生1080'),
         'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞')},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ])
    op = WatchedEnter(test_context)
    with running_operation(op):
        result = op.execute()
        assert result.success, result.status
        assert controller.phase_idx == 11
        assert len(controller.recorded_clicks) == 11
        assert op.zero_checked and op.investment_confirmed
        assert op.confirmed_warnings == {'零装备价值', '未装备武备', '未穿戴队伍装备'}
        assert op.visited == [(name, False) for name in (
            '检测游戏窗口', '恢复启动贝果局', '处理启动仓库', '返回启动仓库上一页', '打开贝果主界面', '备战返回选图',
            '选择雅努斯', '选择高危', '打开备战', '核对零携带', '确认入场并等待加载',
        )]


@pytest.mark.parametrize(
    'failure',
    [
        'timeout',
    ],
)
def test_starting_warehouse_return_failure_stops(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    """返回无效、超时或输入失败均在原节点停止，不能继续选图入场。"""
    controller.set_phases([{'frame': ('贝果-仓库', 'clear_loadout_prepare_warehouse_empty')}])
    op = WatchedEnter(test_context)
    if failure == 'timeout':
        def expire_return_node(wait: float | None = None, wait_round_time: float | None = None) -> None:
            """只推进目标节点的已用时间，不修改系统时钟或真实等待。"""
            if op._current_node.cn == '返回启动仓库上一页' and op.node_clicked:
                op._current_node_start_time -= 21

        monkeypatch.setattr(op, '_after_round_wait', expire_return_node)
    elif failure == 'click_failed':
        original_click = controller.click

        def failed_click(*args: object, **kwargs: object) -> bool:
            """记录实际尝试的位置，同时模拟控制器明确返回失败。"""
            original_click(*args, **kwargs)
            return False

        monkeypatch.setattr(controller, 'click', failed_click)
    with running_operation(op):
        result = op.execute()
        assert not result.success
        expected = {'unchanged': '等待仓库返回备战或研究站入口', 'timeout': '超时', 'click_failed': '点击失败 返回'}
        assert expected[failure] in result.status
        assert [name for name, _ in op.visited] == ['检测游戏窗口', '恢复启动贝果局', '处理启动仓库', '返回启动仓库上一页']
        assert not op.zero_checked and not op.investment_confirmed
        assert len(controller.recorded_clicks) == (4 if failure == 'click_failed' else 1)
        assert all(controller._pos_in_region(pos, (0, 0, 200, 100)) for pos in controller.recorded_clicks)
