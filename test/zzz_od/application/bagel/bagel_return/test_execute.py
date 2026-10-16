"""贝果复用通用返回大世界，页面阻挡不新增专用签到操作。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_entry import BagelFixtureController
from test.harness.fixture_controller import enter_running_state, reset_running_state

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_return import BagelReturn

if TYPE_CHECKING:
    from test.conftest import TestContext

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.fixture
def controller(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch
) -> BagelFixtureController:
    """通用返回识别与按钮使用真资源，避免无关小地图服务触发模型初始化。"""
    controller = BagelFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr(
        test_context.world_patrol_service,
        'cut_mini_map',
        lambda _: MagicMock(play_mask_found=False),
    )
    return controller


@pytest.mark.parametrize(
    'loading_polls,dialogue_polls',
    [
        (16, 4),
    ],
    ids=['long-loading-and-dialogue'],
)
def test_return_waits_for_loading_before_local_reentry(
    test_context: TestContext,
    controller: BagelFixtureController,
    monkeypatch: pytest.MonkeyPatch,
    loading_polls: int,
    dialogue_polls: int,
) -> None:
    """返回和出发切换超过三帧后仍须直接入场，不能重新打开传送地图。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '空局仓库-原生1080'),
                'exit': ('on_click_in', '贝果-仓库', '返回研究站'),
            },
            {
                'frame': ('贝果-局内', '加载-原生1080'),
                'exit': ('on_polls', loading_polls),
            },
            {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
            {
                'frame': ('贝果-研究站', '达塔对话-原生1080'),
                'exit': ('on_click_in', '贝果-研究站', '出发对话'),
            },
            *(
                [
                    {
                        'frame': ('贝果-研究站', '出发切换黑屏-20261006'),
                        'exit': ('on_polls', dialogue_polls),
                    }
                ]
                if dialogue_polls
                else []
            ),
            {
                'frame': ('贝果-研究站', '主界面-原生1080'),
                'exit': ('on_click_in', '贝果-研究站', '前往空洞'),
            },
            {
                'frame': ('贝果-选图', '雅努斯高危-原生1080'),
                'exit': ('on_click_in', '贝果-选图', '前往备战'),
            },
            {
                'frame': ('贝果-备战', '高危零携带-原生1080'),
                'exit': ('on_click_in', '贝果-备战', '前往空洞'),
            },
            {
                'frame': ('贝果-入场确认', '高危零投资-原生1080'),
                'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞'),
            },
            {'frame': ('贝果-局内', '高危A出生-原生1080')},
        ]
    )
    transport = MagicMock(return_value=OperationResult(False, '不应重复传送'))
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_enter.Transport.execute', transport
    )
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
        assert len(controller.recorded_clicks) == 6
    finally:
        reset_running_state(test_context, returning)
        reset_running_state(test_context, entering)


@pytest.mark.parametrize(
    'after_dialogue',
    [
        False,
    ],
)
def test_return_blocker_uses_generic_back_and_stops_in_world(
    test_context: TestContext,
    controller: BagelFixtureController,
    after_dialogue: bool,
) -> None:
    """加载和出发后的明确阻挡均使用通用返回，不误认为入口切换黑屏。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '空局仓库-原生1080'),
                'exit': ('on_click_in', '贝果-仓库', '返回研究站'),
            },
            *(
                [
                    {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
                    {
                        'frame': ('贝果-研究站', '达塔对话-原生1080'),
                        'exit': ('on_click_in', '贝果-研究站', '出发对话'),
                    },
                ]
                if after_dialogue
                else []
            ),
            {
                'frame': ('画面-通用', '贝果返回阻挡页'),
                'exit': ('on_click_in', '画面-通用', '返回'),
            },
            {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080')},
        ]
    )
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


def test_generic_return_is_bounded_when_page_never_closes(
    test_context: TestContext,
    controller: BagelFixtureController,
) -> None:
    """通用返回无法关闭阻挡时耗尽时限即停止，不反复创建新恢复操作。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '空局仓库-原生1080'),
                'exit': ('on_click_in', '贝果-仓库', '返回研究站'),
            },
            {'frame': ('画面-通用', '贝果返回阻挡页')},
        ]
    )
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
