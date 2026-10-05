"""退出入口用原生画面核对路由与输入，面板关闭仍要重新截图。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.fixture_controller import enter_running_state, reset_running_state
from test.zzz_od.application.bagel.test_flows import BagelFixtureController

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_exit import BagelExit

if TYPE_CHECKING:
    from test.conftest import TestContext

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.fixture
def controller(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> BagelFixtureController:
    """保留真实识别，只有按键与点击使用假控制器。"""
    controller = BagelFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return controller


@pytest.mark.parametrize('page,state,kind,status,keys', [
    ('贝果-仓库', '空局仓库-原生1080', 'SUCCESS', '已到结算仓库', []),
    ('贝果-退出确认', '主动退出-原生1080', 'SUCCESS', '已到退出确认', []),
    ('贝果-局内', '暂停菜单-原生1080', 'SUCCESS', '已到暂停菜单', []),
    ('贝果-结算', '高危空局失败-原生1080', 'SUCCESS', '已到贝果结算', []),
    ('贝果-局内', '武备箱搜查中-r07', 'WAIT', '关闭局内面板后重新检查退出画面', ['esc']),
    ('贝果-局内', '电子保险箱搜索完成', 'WAIT', '关闭局内面板后重新检查退出画面', ['esc']),
    ('贝果-局内', '电子保险箱第1轮小圈', 'WAIT', '关闭局内面板后重新检查退出画面', ['esc']),
    ('贝果-局内', '高危A出生-原生1080', 'SUCCESS', None, ['esc']),
    ('贝果-局内', '加载-原生1080', 'RETRY', '未识别贝果局内画面', []),
], ids=['warehouse', 'confirm', 'menu', 'defeat', 'box', 'safe', 'unlock', 'hud', 'unknown'])
def test_open_menu_routes_and_inputs(
    test_context: TestContext, controller: BagelFixtureController,
    page: str, state: str, kind: str, status: str | None, keys: list[str],
) -> None:
    """不同入口只返回相应状态；面板只按 Esc，未知画面不发送输入。"""
    controller.set_phases([{'frame': (page, state)}])
    op = BagelExit(test_context)
    op.screenshot()
    result = op.open_menu()
    assert result.result == OperationRoundResultEnum[kind]
    assert result.status == status
    assert controller.recorded_inputs == keys
    assert controller.recorded_clicks == []


@pytest.mark.parametrize('panel', [
    '武备箱搜查中-r07', '电子保险箱搜索完成', '电子保险箱第1轮小圈',
], ids=['box', 'safe', 'unlock'])
def test_panel_close_rechecks_world_before_exit(
    test_context: TestContext, controller: BagelFixtureController, panel: str,
) -> None:
    """面板关闭后的新帧必须先核对局内，再打开菜单并执行专用退出。"""
    controller.set_phases([
        {'frame': ('贝果-局内', panel), 'key': 'esc'},
        {'frame': ('贝果-局内', '高危A出生-原生1080'), 'key': 'esc'},
        {'frame': ('贝果-局内', '暂停菜单-原生1080'),
         'exit': ('on_click_in', '战斗-菜单', '按钮-退出战斗')},
        {'frame': ('贝果-退出确认', '主动退出-原生1080'),
         'exit': ('on_click_in', '贝果-退出确认', '确认')},
        {'frame': ('贝果-结算', '高危空局失败-原生1080'),
         'exit': ('on_click_in', '贝果-结算', '继续')},
        {'frame': ('贝果-仓库', '空局仓库-原生1080')},
    ])
    op = BagelExit(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success and result.status == '已到结算仓库'
        assert controller.phase_idx == 5
        assert controller.recorded_inputs == ['esc', 'esc']
        assert len(controller.recorded_clicks) == 3
    finally:
        reset_running_state(test_context, op)
