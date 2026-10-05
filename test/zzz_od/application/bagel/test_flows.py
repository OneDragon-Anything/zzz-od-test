from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_return import BagelReturn

if TYPE_CHECKING:
    from test.conftest import TestContext


class BagelFixtureController(FixtureController):
    """只有剧本指定的交互键才推进，其他输入不能跳过画面。"""

    def btn_press(self, key: str, press_time: float | None = None) -> None:
        """记录按键并匹配当前画面需要的输入。"""
        self.recorded_inputs.append(key)
        if self._phases[self.phase_idx].get('key') == key:
            self._advance_phase()

    def interact(
        self, press: bool = False, press_time: float | None = None, release: bool = False,
    ) -> None:
        """达塔交互按 F 推进。"""
        self.btn_press('f', press_time)


class WatchedEnter(WatchdogOperationMixin, BagelEnter):
    """限制测试等待轮数，防止识别回归挂住。"""

    watchdog_max_rounds: int = 45


class WatchedExit(WatchdogOperationMixin, BagelExit):
    """限制测试等待轮数，防止识别回归挂住。"""

    watchdog_max_rounds: int = 30


class WatchedOpenBox(WatchdogOperationMixin, BagelOpenBox):
    """限制开箱搜查等待轮数。"""

    watchdog_max_rounds: int = 20


def test_open_box_retries_missed_interaction_once(
    test_context: TestContext, controller: BagelFixtureController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一次 F 未生效时限次补按，进入面板后不触发全部拾取。"""
    controller.set_phases([
        {'frame': ('贝果-局内', '雅努斯箱前-r07-32s'), 'key': 'f'},
        {'frame': ('贝果-局内', '雅努斯箱前-r07-32s'), 'key': 'f'},
        {'frame': ('贝果-局内', '武备箱搜查中-r07'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '武备箱搜索结果-r07')},
    ])
    op = WatchedOpenBox(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert controller.recorded_inputs == ['f', 'f']
    finally:
        reset_running_state(test_context, op)


def test_open_box_does_not_press_while_search_panel_open(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """搜查面板还在时不能补按，避免触发全部拾取。"""
    controller.set_phases([{'frame': ('贝果-局内', '武备箱搜查中-r07')}])
    op = WatchedOpenBox(test_context)
    op.screenshot()
    op.recovery.interactions = 1
    op.recovery.last_interact_at = op.recovery.clock() - 2
    assert op.wait_search().status == '已进入武备箱搜查'
    assert controller.recorded_inputs == []


def test_open_box_retries_after_search_panel_closes(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """敌袭打断搜查后回到箱前提示，允许再按一次 F。"""
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯箱前-r07-32s')}])
    op = WatchedOpenBox(test_context)
    op.screenshot()
    op.recovery.interactions = 1
    op.recovery.last_interact_at = op.recovery.clock() - 2
    assert op.wait_search().status == '武备箱未打开，补按一次交互'
    assert controller.recorded_inputs == ['f']


def test_open_box_stops_after_three_missed_interactions(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """三次输入均未打开时提前终止，不允许第四次交互。"""
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯箱前-r07-32s')}])
    op = WatchedOpenBox(test_context)
    op.screenshot()
    op.recovery.interactions = 3
    op.recovery.last_interact_at = op.recovery.clock() - 2
    assert op.wait_search().status == '容器开箱交互已达3次上限'
    assert controller.recorded_inputs == []


def test_open_box_live_failure_can_retry(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """真实开箱超时现场仍有明确交互提示，允许唯一一次补按。"""
    from one_dragon.utils import cv2_utils

    root = next(path for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')
    # 直接给节点框架 RGB 原图，不经过有损转换。
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯箱前-r07-32s')}])
    op = WatchedOpenBox(test_context)
    op.last_screenshot = cv2_utils.read_image(str(root / 'screens/贝果-局内/批次失败-开箱未进入面板.webp'))
    op.last_screenshot_time = 3
    op.recovery.interactions = 1
    op.recovery.last_interact_at = op.recovery.clock() - 3
    assert op.wait_search().status == '武备箱未打开，补按一次交互'
    assert controller.recorded_inputs == ['f']


class WatchedReturn(WatchdogOperationMixin, BagelReturn):
    """限制返回流程轮数，避免画面剧本回归后无限等待。"""

    watchdog_max_rounds: int = 25


@pytest.fixture
def controller(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
) -> BagelFixtureController:
    """使用真截图、OCR 和区域，只替换输入及等待。"""
    result = BagelFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', result)
    return result


@pytest.mark.parametrize('state', [
    '达塔前-原生1080', '返回研究站达塔前-原生1080', '达塔对话-原生1080',
])
@pytest.mark.parametrize('transport_success', [True, False])
def test_reception_start_uses_transport_without_local_interaction(
    test_context: TestContext, controller: BagelFixtureController,
    monkeypatch: pytest.MonkeyPatch, state: str, transport_success: bool,
) -> None:
    """达塔前和对话起点均先交给通用传送，失败时不改为就地交互。"""
    controller.set_phases([{'frame': ('贝果-研究站', state)}])
    op = BagelEnter(test_context)
    op.screenshot()
    transport = MagicMock(return_value=OperationResult(transport_success, '传送结果'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)

    result = op.open_hub()

    transport.assert_called_once()
    assert controller.recorded_clicks == []
    assert controller.recorded_inputs == []
    assert op.transport_started == transport_success
    assert result.is_fail == (not transport_success)
    assert result.status == ('等待研究站传送落地' if transport_success else '传送结果')


def test_enter_from_reception(
    test_context: TestContext, controller: BagelFixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """达塔起点先传送，再交互入场；验证各 WAIT 画面与点击的衔接。"""
    phases = [
        {'frame': ('贝果-研究站', '达塔前-原生1080')},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
        {'frame': ('贝果-研究站', '达塔对话-原生1080'), 'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        {'frame': ('贝果-研究站', '主界面-原生1080'), 'exit': ('on_click_in', '贝果-研究站', '前往空洞')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'), 'exit': ('on_click_in', '贝果-选图', '雅努斯')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'), 'exit': ('on_click_in', '贝果-选图', '高危')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'), 'exit': ('on_click_in', '贝果-选图', '前往备战')},
        {'frame': ('贝果-备战', '高危零携带-原生1080'), 'exit': ('on_click_in', '贝果-备战', '前往空洞')},
    ]
    phases.extend(
        {'frame': ('贝果-入场确认', f'{state}-原生1080'), 'exit': ('on_click_in', '贝果-入场确认', '确认')}
        for state in ('高危零装备价值', '未装备武备', '未穿戴队伍装备')
    )
    phases.extend([
        {'frame': ('贝果-入场确认', '高危零投资-原生1080'),
         'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞')},
        {'frame': ('贝果-局内', '加载-原生1080'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ])
    controller.set_phases(phases)

    def transport_to_reception() -> OperationResult:
        """替代通用传送子操作，必须在任何就地交互之前调用。"""
        assert controller.phase_idx == 0
        assert controller.recorded_inputs == []
        assert controller.recorded_clicks == []
        controller._advance_phase()
        return OperationResult(True, '传送完成')

    transport = MagicMock(side_effect=transport_to_reception)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    op = WatchedEnter(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == '已进入雅努斯高危'
        assert controller.phase_idx == len(phases) - 1
        assert len(op.confirmed_warnings) == 3
        assert op.investment_confirmed
        assert controller.recorded_inputs == ['f']
        transport.assert_called_once()
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('already_defeated', [False, True])
def test_exit_to_warehouse(
    test_context: TestContext, controller: BagelFixtureController, already_defeated: bool,
) -> None:
    """主动退出与已死亡两条分支都应停在仓库，不能自动转移或返回。"""
    phases = [] if already_defeated else [
        {'frame': ('贝果-局内', '六昏街南站出生-原生1080'), 'key': 'esc'},
        {'frame': ('贝果-局内', '暂停菜单-原生1080'), 'exit': ('on_click_in', '战斗-菜单', '按钮-退出战斗')},
        {'frame': ('贝果-退出确认', '主动退出-原生1080'), 'exit': ('on_click_in', '贝果-退出确认', '确认')},
        {'frame': ('贝果-局内', '加载-原生1080'), 'exit': ('on_polls', 2)},
    ]
    phases.extend([
        {'frame': ('贝果-结算', '高危空局失败-原生1080'), 'exit': ('on_click_in', '贝果-结算', '继续')},
        {'frame': ('贝果-局内', '加载-原生1080'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-仓库', '空局仓库-原生1080')},
    ])
    controller.set_phases(phases)
    op = WatchedExit(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == '已到结算仓库'
        assert controller.phase_idx == len(phases) - 1
        assert len(controller.recorded_clicks) == (1 if already_defeated else 3)
    finally:
        reset_running_state(test_context, op)


def test_return_to_hub_after_warehouse(
    test_context: TestContext, controller: BagelFixtureController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """仓库返回后先等 HUD，按一次 F 才出现达塔对话并回到入口。"""
    phases = [
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        {'frame': ('贝果-局内', '加载-原生1080'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
        {'frame': ('贝果-研究站', '达塔对话-原生1080'),
         'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        {'frame': ('贝果-研究站', '主界面-原生1080')},
    ]
    controller.set_phases(phases)
    events: list[tuple[str, int, float | None]] = []
    original_interact = controller.interact

    def record_interact(
        press: bool = False, press_time: float | None = None, release: bool = False,
    ) -> None:
        """记录按 F 时所在画面，再使用剧本正常推进。"""
        events.append(('interact', controller.phase_idx, None))
        original_interact(press=press, press_time=press_time, release=release)

    monkeypatch.setattr(controller, 'interact', record_interact)
    op = WatchedReturn(test_context)
    original_wait = op._after_round_wait

    def record_wait(wait: float | None = None, wait_round_time: float | None = None) -> None:
        """记录逻辑等待，并使用受控时钟推进。"""
        if wait is not None:
            events.append(('wait', controller.phase_idx, wait))
        original_wait(wait=wait, wait_round_time=wait_round_time)

    monkeypatch.setattr(op, '_after_round_wait', record_wait)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == '已返回贝果入口'
        assert controller.phase_idx == len(phases) - 1
        assert controller.recorded_inputs == ['f']
        assert events.index(('wait', 2, 1)) < events.index(('interact', 2, None))
        assert len(controller.recorded_clicks) == 2
    finally:
        reset_running_state(test_context, op)


def test_return_accepts_hub_without_interaction(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """返回途中已到主界面时直接完成，不能继续等大世界 HUD 或再按 F。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        {'frame': ('贝果-局内', '加载-原生1080'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-研究站', '返回后已到主界面-4k缩放')},
    ])
    op = WatchedReturn(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == '已返回贝果入口'
        assert controller.recorded_inputs == []
        assert len(controller.recorded_clicks) == 1
    finally:
        reset_running_state(test_context, op)


def test_return_confirms_extraction_reward_once(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """满仓后返回可能弹出撤离奖励确认，必须确认后才等待研究站。"""
    controller.set_phases([
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        {'frame': ('贝果-仓库', '撤离奖励提示-20260924'),
         'exit': ('on_click_in', '贝果-仓库', '撤离奖励确认')},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
        {'frame': ('贝果-研究站', '达塔对话-原生1080'),
         'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        {'frame': ('贝果-研究站', '主界面-原生1080')},
    ])
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


@pytest.mark.parametrize('prepare_state', ['零携带-原生1080', '城郊高危零携带-20260926'])
def test_enter_from_prepare_reselects_map_before_entering(
    test_context: TestContext, controller: BagelFixtureController, prepare_state: str,
) -> None:
    """直接从备战开始也必须先返回选图，重新选择雅努斯高危。"""
    phases = [
        {'frame': ('贝果-备战', prepare_state), 'exit': ('on_click_in', '菜单', '返回')},
        {'frame': ('贝果-选图', '城郊高危-20260926'), 'exit': ('on_click_in', '贝果-选图', '雅努斯')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'), 'exit': ('on_click_in', '贝果-选图', '高危')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'), 'exit': ('on_click_in', '贝果-选图', '前往备战')},
        {'frame': ('贝果-备战', '高危零携带-原生1080'), 'exit': ('on_click_in', '贝果-备战', '前往空洞')},
        {'frame': ('贝果-入场确认', '高危零投资-原生1080'), 'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞')},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ]
    controller.set_phases(phases)
    op = WatchedEnter(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert controller.phase_idx == len(phases) - 1
        assert controller.click_hit_area('菜单', '返回')
        assert controller.click_hit_area('贝果-选图', '雅努斯')
        assert controller.click_hit_area('贝果-选图', '高危')
    finally:
        reset_running_state(test_context, op)


def test_open_box_enters_search_before_result(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """箱前只按一次 F，搜查面板出现便交给入箱操作。"""
    phases = [
        {'frame': ('贝果-局内', '雅努斯箱前-r07-32s'), 'key': 'f'},
        {'frame': ('贝果-局内', '武备箱搜查中-r07'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '武备箱搜索结果-r07')},
    ]
    controller.set_phases(phases)
    op = WatchedOpenBox(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == '已进入武备箱搜查'
        assert controller.phase_idx == 1
        assert controller.recorded_inputs == ['f']
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


def test_open_box_already_searching_skips_f(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """已在武备箱搜查面板时直接交给入箱，不重复交互。"""
    phases = [
        {'frame': ('贝果-局内', '武备箱搜查中-r07'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '武备箱搜索结果-r07')},
    ]
    controller.set_phases(phases)
    op = WatchedOpenBox(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == '已进入武备箱搜查'
        assert controller.phase_idx == 1
        assert controller.recorded_inputs == []
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


def test_open_box_without_prompt_stops(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """普通局内 HUD 没有武备箱提示时停止，不发送 F。"""
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯出生-r07-30s')}])
    op = WatchedOpenBox(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert result.status == '容器提示消失，需要重新靠近'
        assert controller.recorded_inputs == []
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


def test_open_box_waits_without_attack_button(
    test_context: TestContext, controller: BagelFixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """即使箱前提示持续存在，没有普通攻击按钮也不能发送交互。"""
    controller.set_phases([{'frame': ('贝果-局内', '雅努斯箱前-r07-32s')}])
    op = WatchedOpenBox(test_context)
    op.screenshot()
    rect = test_context.screen_loader.get_area('战斗画面', '按键-普通攻击').rect
    op.last_screenshot[rect.y1:rect.y2, rect.x1:rect.x2] = 0
    for _ in range(3):
        assert op.open_box().result == OperationRoundResultEnum.WAIT
    assert controller.recorded_inputs == []


def test_exit_confirm_waits_until_dialog_disappears(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """确认点击没生效时仍停在确认节点，不能提前等结算。"""
    controller.set_phases([
        {'frame': ('贝果-退出确认', '主动退出-原生1080')},
    ])
    op = WatchedExit(test_context)
    op.screenshot()
    assert op.confirm_exit().result == OperationRoundResultEnum.WAIT
    op.screenshot()
    assert op.confirm_exit().result == OperationRoundResultEnum.WAIT
    assert len(controller.recorded_clicks) == 2


def test_exit_result_keeps_clicking_continue_until_it_disappears(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """结算「继续」点了还在时留在本节点重试，不能空等仓库。"""
    controller.set_phases([
        {'frame': ('贝果-结算', '高危空局失败-原生1080')},
    ])
    op = WatchedExit(test_context)
    op.screenshot()
    assert op.wait_result().result == OperationRoundResultEnum.WAIT
    op.screenshot()
    assert op.wait_result().result == OperationRoundResultEnum.WAIT
    assert len(controller.recorded_clicks) == 2


def test_return_retries_interaction_only_at_reception(
    test_context: TestContext, controller: BagelFixtureController,
) -> None:
    """落地后首次 F 未生效，仍在达塔前时允许补按并读取新画面。"""
    controller.set_phases([
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'key': 'f'},
        {'frame': ('贝果-研究站', '达塔对话-原生1080')},
    ])
    op = WatchedReturn(test_context)
    op.screenshot()
    result = op.open_hub()
    assert not result.is_success
    assert controller.recorded_inputs == ['f']
    assert controller.phase_idx == 1
