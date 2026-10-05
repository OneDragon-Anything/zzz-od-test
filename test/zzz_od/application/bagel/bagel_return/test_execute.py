"""贝果复用通用返回大世界，页面阻挡不新增专用签到操作。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import enter_running_state, reset_running_state
from test.zzz_od.application.bagel.test_flows import BagelFixtureController

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_return import BagelReturn

if TYPE_CHECKING:
    from test.conftest import TestContext

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.fixture
def controller(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> BagelFixtureController:
    """通用返回识别与按钮使用真资源，避免无关小地图服务触发模型初始化。"""
    controller = BagelFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr(test_context.world_patrol_service, 'cut_mini_map',
                        lambda _: MagicMock(play_mask_found=False))
    return controller


def test_return_blocker_uses_generic_back_and_stops_in_world(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """仓库返回插入已有阻挡截图，通用返回仅点击左上返回，再交正式任务重查入场。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        {'frame': ('画面-通用', '贝果返回阻挡页'),
         'exit': ('on_click_in', '画面-通用', '返回')},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080')},
    ])
    op = BagelReturn(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success and result.status == '已返回大世界'
        assert op.world_recovery_attempted
        assert controller.phase_idx == 2
        assert len(controller.recorded_clicks) == 2
        assert controller.click_hit_area('画面-通用', '返回')
        assert controller.recorded_inputs == []
    finally:
        reset_running_state(test_context, op)


def test_enter_blocker_returns_world_then_restarts_entry(
    test_context: TestContext, controller: BagelFixtureController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首次或额外入场复用通用返回，回到大世界才传送并核验零携带与投资。"""
    phases = [
        {'frame': ('画面-通用', '贝果返回阻挡页'),
         'exit': ('on_click_in', '画面-通用', '返回')},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080')},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
        {'frame': ('贝果-研究站', '达塔对话-原生1080'),
         'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        {'frame': ('贝果-研究站', '主界面-原生1080'),
         'exit': ('on_click_in', '贝果-研究站', '前往空洞')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '雅努斯')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '高危')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '前往备战')},
        {'frame': ('贝果-备战', '高危零携带-原生1080'),
         'exit': ('on_click_in', '贝果-备战', '前往空洞')},
        {'frame': ('贝果-入场确认', '高危零投资-原生1080'),
         'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞')},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ]
    controller.set_phases(phases)

    def transport(op: object) -> OperationResult:
        """通用返回已经到大世界后，才由传送接续正式入场。"""
        assert controller.phase_idx == 1
        assert controller.recorded_inputs == []
        assert len(controller.recorded_clicks) == 1
        controller._advance_phase()
        return OperationResult(True, '已传送')

    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    op = BagelEnter(test_context, allow_world_recovery=True)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success and result.status == '已进入雅努斯高危'
        assert op.world_recovery_attempted
        assert not op.allow_clear_loadout and not op.clear_attempted
        assert controller.phase_idx == len(phases) - 1
        assert controller.recorded_inputs == ['f']
    finally:
        reset_running_state(test_context, op)


def test_generic_return_is_bounded_when_page_never_closes(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """通用返回无法关闭阻挡时耗尽时限即停止，不反复创建新恢复操作。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        {'frame': ('画面-通用', '贝果返回阻挡页')},
    ])
    op = BagelReturn(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert op.world_recovery_attempted and controller.phase_idx == 1
        assert 2 <= len(controller.recorded_clicks) <= 42
        assert controller.recorded_inputs == []
    finally:
        reset_running_state(test_context, op)
