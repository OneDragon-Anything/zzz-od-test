from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from test.harness.bagel_entry import BagelFixtureController as BagelFixtureController
from test.harness.bagel_entry import WatchedEnter as WatchedEnter
from test.harness.bagel_entry import WatchedExit as WatchedExit
from test.harness.bagel_entry import WatchedOpenBox as WatchedOpenBox
from test.harness.bagel_entry import WatchedReturn as WatchedReturn
from test.harness.bagel_entry import controller as controller
from test.harness.fixture_controller import (
    enter_running_state,
    reset_running_state,
)

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_open_box_live_failure_can_retry(
    test_context: TestContext,
    controller: BagelFixtureController,
) -> None:
    """真实开箱超时现场仍有明确交互提示，允许唯一一次补按。"""
    from one_dragon.utils import cv2_utils

    root = next(
        path for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test'
    )
    # 直接给节点框架 RGB 原图，不经过有损转换。
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯箱前-r07-32s')}])
    op = WatchedOpenBox(test_context)
    op.last_screenshot = cv2_utils.read_image(
        str(root / 'screens/贝果-局内/批次失败-开箱未进入面板.webp')
    )
    op.last_screenshot_time = 3
    op.recovery.interactions = 1
    op.recovery.last_interact_at = op.recovery.clock() - 3
    assert op.wait_search().status == '武备箱未打开，补按一次交互'
    assert controller.recorded_inputs == ['f']


def test_return_confirms_extraction_reward_once(
    test_context: TestContext,
    controller: BagelFixtureController,
) -> None:
    """满仓后返回可能弹出撤离奖励确认，必须确认后才等待研究站。"""
    controller.set_phases(
        [
            {
                'frame': ('贝果-仓库', '空局仓库-原生1080'),
                'exit': ('on_click_in', '贝果-仓库', '返回研究站'),
            },
            {
                'frame': ('贝果-仓库', '撤离奖励提示-20260924'),
                'exit': ('on_click_in', '贝果-仓库', '撤离奖励确认'),
            },
            {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
            {
                'frame': ('贝果-研究站', '达塔对话-原生1080'),
                'exit': ('on_click_in', '贝果-研究站', '出发对话'),
            },
            {'frame': ('贝果-研究站', '主界面-原生1080')},
        ]
    )
    op = WatchedReturn(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == '已返回贝果入口'
        assert controller.phase_idx == 4
        assert controller.recorded_inputs == ['f']
        assert len(controller.recorded_clicks) == 3
    finally:
        reset_running_state(test_context, op)
