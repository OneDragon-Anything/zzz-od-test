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


@pytest.mark.parametrize('loading_polls', [4, 16])
@pytest.mark.parametrize('dialogue_polls', [0, 4])
def test_return_waits_for_loading_before_local_reentry(
    test_context: TestContext, controller: BagelFixtureController,
    monkeypatch: pytest.MonkeyPatch, loading_polls: int, dialogue_polls: int,
) -> None:
    """返回和出发切换超过三帧后仍须直接入场，不能重新打开传送地图。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        {'frame': ('贝果-局内', '加载-原生1080'), 'exit': ('on_polls', loading_polls)},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
        {'frame': ('贝果-研究站', '达塔对话-原生1080'),
         'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        *([{'frame': ('贝果-研究站', '出发切换黑屏-20261006'),
            'exit': ('on_polls', dialogue_polls)}] if dialogue_polls else []),
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
    ])
    transport = MagicMock(return_value=OperationResult(False, '不应重复传送'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    returning = BagelReturn(test_context)
    entering = BagelEnter(test_context)
    enter_running_state(test_context)
    try:
        returned = returning.execute()
        result = entering.execute() if returned.success else returned
        transport.assert_not_called()
        assert returned.success and returned.status == '已返回贝果入口'
        assert not returning.world_recovery_attempted
        assert result.success and result.status == '已进入雅努斯高危'
        assert controller.phase_idx == len(controller._phases) - 1
        assert controller.recorded_inputs == ['f']
        assert len(controller.recorded_clicks) == 8
    finally:
        reset_running_state(test_context, returning)
        reset_running_state(test_context, entering)


@pytest.mark.parametrize('recovery_success', [False, True])
@pytest.mark.parametrize('stage', ['等待研究站加载', '打开贝果入口'])
def test_loading_timeout_attempts_world_recovery_once(
    test_context: TestContext, controller: BagelFixtureController,
    monkeypatch: pytest.MonkeyPatch, recovery_success: bool, stage: str,
) -> None:
    """两个过渡节点的真实超时边只恢复一次，黑屏时不补按 F。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        *([
            {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
            {'frame': ('贝果-研究站', '达塔对话-原生1080'),
             'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        ] if stage == '打开贝果入口' else []),
        {'frame': ('贝果-研究站', '出发切换黑屏-20261006')},
    ])
    clicks = 2 if stage == '打开贝果入口' else 1
    inputs = ['f'] if stage == '打开贝果入口' else []
    op = BagelReturn(test_context)
    recovery = MagicMock(return_value=OperationResult(recovery_success, '页面恢复结果'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_return.BackToNormalWorld.execute', recovery)
    original_wait = op._after_round_wait

    def expire_loading(
        wait: float | None = None, wait_round_time: float | None = None,
    ) -> None:
        """只提前结束目标节点的计时，保持正式操作图和恢复次数限制。"""
        original_wait(wait=wait, wait_round_time=wait_round_time)
        if op._current_node.cn == stage and controller.phase_idx == len(controller._phases) - 1:
            assert not op.world_recovery_attempted
            assert len(controller.recorded_clicks) == clicks
            assert controller.recorded_inputs == inputs
            op._current_node_start_time -= 26

    monkeypatch.setattr(op, '_after_round_wait', expire_loading)
    enter_running_state(test_context)
    try:
        result = op.execute()
        recovery.assert_called_once()
        assert result.success == recovery_success
        assert result.status == ('已返回大世界' if recovery_success else '页面恢复结果')
        assert op.world_recovery_attempted
        assert controller.phase_idx == len(controller._phases) - 1
        assert len(controller.recorded_clicks) == clicks
        assert controller.recorded_inputs == inputs
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('after_dialogue', [False, True])
def test_return_blocker_uses_generic_back_and_stops_in_world(
    test_context: TestContext, controller: BagelFixtureController, after_dialogue: bool,
) -> None:
    """加载和出发后的明确阻挡均使用通用返回，不误认为入口切换黑屏。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        *([
            {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
            {'frame': ('贝果-研究站', '达塔对话-原生1080'),
             'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        ] if after_dialogue else []),
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
        assert controller.phase_idx == len(controller._phases) - 1
        assert len(controller.recorded_clicks) == (3 if after_dialogue else 2)
        assert controller.click_hit_area('画面-通用', '返回')
        assert controller.recorded_inputs == (['f'] if after_dialogue else [])
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
