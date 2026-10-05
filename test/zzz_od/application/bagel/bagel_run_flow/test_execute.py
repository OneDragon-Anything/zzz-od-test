"""公共执行器的勾选顺序、前置画面及失败状态。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_operation import (
    BagelOperation,
    BagelRecoverableFailure,
)
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow

if TYPE_CHECKING:
    from test.conftest import TestContext

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.mark.parametrize('areas,ready', [
    ({'大保险解锁提示'}, True),
    ({'电子保险箱标题', '搜查安全箱', '搜查进行中'}, True),
    ({'电子保险箱标题', '搜查安全箱'}, False),
    ({'搜查容器标题', '搜查安全箱', '搜查完成'}, False),
])
def test_unlock_requires_ring_or_safe_search(
    areas: set[str], ready: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """允许已解锁的保险箱，标题不完整或武备箱不能当作解锁完成。"""
    flow = load_published_flow('janus_high_a')
    op = BagelRunFlow(MagicMock(), flow)
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_has', lambda area: area in areas)
    step = next(s for s in flow.steps if s.action == 'unlock')
    assert (op.precondition(step) is None) is ready


def test_safe_interact_then_unlock_accepts_existing_search(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第十一按 F 后直接进入搜查，第十二确认已解锁，不再按 F 或报前置错误。"""
    controller = FixtureController(test_context)
    controller.set_phases([
        {'frame': ('贝果-局内', '电子保险箱交互-HUD错字-20260930')},
        {'frame': ('贝果-局内', '电子保险箱搜索完成')},
    ])
    monkeypatch.setattr(test_context, 'controller', controller)
    press = MagicMock(side_effect=lambda **_: controller._advance_phase())
    monkeypatch.setattr(controller, 'interact', press)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.release_flow_inputs', lambda _: None)
    flow = load_published_flow('janus_high_a')
    selected = tuple(s.id for s in flow.steps if s.target == 'safe' and s.action in ('interact', 'unlock'))
    events: list[dict[str, object]] = []
    op = BagelRunFlow(test_context, flow, selected, on_event=events.append)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert [e['step_id'] for e in events if e['kind'] == 'done'] == list(selected)
        press.assert_called_once_with(press=True, press_time=0.2, release=True)
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize(
    'failed_status', [None, '未打开容器', BagelOperation.STATUS_DEFEATED,
                      BagelOperation.STATUS_INTERRUPTED]
)
def test_sequence_stops_at_failed_step(
    failed_status: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """选中范围只运行对应动作，普通失败和整局失败原样透传。"""
    flow = load_published_flow('janus_high_b')
    events = []
    op = BagelRunFlow(
        MagicMock(), flow, ('open_box', 'store_box'), on_event=events.append
    )
    monkeypatch.setattr(op, 'precondition', lambda _: None)
    child = MagicMock()
    child.execute.return_value = OperationResult(
        failed_status is None, failed_status or '开箱完成'
    )
    monkeypatch.setattr(op, 'build_operation', lambda _: child)
    first = op.run_step()
    if failed_status:
        expected = failed_status
        assert first.is_fail and first.status == expected
        if expected == BagelOperation.STATUS_CONTAINER_FAILED:
            assert first.data == failed_status
        assert op.index == 2
        assert [e['kind'] for e in events] == ['start', 'failed']
    else:
        assert first.result == OperationRoundResultEnum.WAIT and op.index == 3
        assert op.run_step().is_success
        assert child.execute.call_count == 2


@pytest.mark.parametrize('action,target', [
    ('move', None), ('approach', 'box'), ('approach', 'safe'),
    ('interact', 'box'), ('interact', 'safe'), ('unlock', 'safe'),
    ('store', 'box'), ('store', 'safe'), ('close', 'box'), ('close', 'safe'),
])
def test_each_action_propagates_defeat_without_advancing(
    action: str, target: str | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实动作派发的每种类型都原样返回失败，后续步骤不得执行。"""
    flow = load_published_flow('janus_high_a')
    step = next(s for s in flow.steps if s.action == action and s.target == target)
    op = BagelRunFlow(MagicMock(), flow, (step.id, 'exit'))
    child = op.build_operation(step)
    execute = MagicMock(return_value=OperationResult(False, BagelOperation.STATUS_DEFEATED))
    monkeypatch.setattr(type(child), 'execute', execute)
    monkeypatch.setattr(op, 'precondition', lambda _: None)
    result = op.run_step()
    assert result.is_fail and result.status == BagelOperation.STATUS_DEFEATED
    assert op.cursor == 0 and op.flow.steps[op.index] == step
    execute.assert_called_once()


@pytest.mark.parametrize('action', ['move', 'approach'])
def test_navigation_success_requires_expected_arrival(
    action: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """子操作成功但没有到达本步目标时，不得推进到后续交互。"""
    flow = load_published_flow('janus_high_b')
    if action == 'move':
        flow = load_published_flow('janus_high_a')
    step = next(s for s in flow.steps if s.action == action)
    op = BagelRunFlow(MagicMock(), flow, (step.id, 'exit'))
    monkeypatch.setattr(op, 'precondition', lambda _: None)
    child = MagicMock()
    child.execute.return_value = OperationResult(True, '不是预期到达状态')
    monkeypatch.setattr(op, 'build_operation', lambda _: child)
    assert op.run_step().is_fail
    assert op.cursor == 0


def test_precondition_failure_never_builds_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """画面不符不补开容器或执行前面的步骤。"""
    op = BagelRunFlow(MagicMock(), load_published_flow('janus_high_b'), ('store_box',))
    monkeypatch.setattr(op, 'precondition', lambda _: '未识别对应容器搜查面板')
    build = MagicMock()
    monkeypatch.setattr(op, 'build_operation', build)
    assert op.run_step().is_fail
    build.assert_not_called()


def test_non_contiguous_selection_skips_unchecked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只执行勾选动作，输入清单逆序也按流程排列，没有隐含暂停。"""
    flow = load_published_flow('janus_high_b')
    op = BagelRunFlow(MagicMock(), flow, ('exit', 'open_box'))
    assert op.step_ids == ('open_box', 'exit')
    seen = []
    monkeypatch.setattr(op, 'precondition', lambda step: seen.append(step.action))
    child = MagicMock()
    child.execute.return_value = OperationResult(True, '完成')
    monkeypatch.setattr(op, 'build_operation', lambda _: child)
    assert op.run_step().result == OperationRoundResultEnum.WAIT
    assert op.index == len(flow.steps) - 1
    assert op.run_step().is_success
    assert seen == ['interact', 'exit']
    assert child.execute.call_count == 2


@pytest.mark.parametrize('chosen', [(), ('missing',), ('spawn', 'spawn')])
def test_invalid_selection_rejected(chosen: tuple[str, ...]) -> None:
    """空勾选、未知标识和重复项不能触发执行。"""
    with pytest.raises(ValueError):
        BagelRunFlow(MagicMock(), load_published_flow('janus_high_b'), chosen)


@pytest.mark.parametrize(
    'action_index,areas,expected',
    [
        (2, {'按键-普通攻击', '武备箱交互', '交互F键'}, None),
        (2, {'按键-普通攻击', '武备箱交互'}, '未发现武备箱交互及F图标'),
        (3, {'搜查容器标题', '搜查安全箱', '搜查进行中'}, None),
        (3, {'电子保险箱标题', '搜查安全箱', '搜查完成'}, '未识别对应容器搜查面板'),
        (3, {'按键-普通攻击'}, BagelOperation.STATUS_INTERRUPTED),
        (3, set(), '未识别对应容器搜查面板'),
        (5, set(), '未识别贝果局内画面'),
        (5, {'按键-普通攻击', '搜查容器标题'}, '请先执行关闭搜查面板步骤'),
        (1, {'按键-普通攻击', '电子保险箱标题'}, '请先执行关闭搜查面板步骤'),
        (5, {'按键-普通攻击', '大保险解锁提示'}, '请先完成电子保险箱解锁并关闭搜查面板'),
    ],
)
def test_action_preconditions(
    action_index: int,
    areas: set[str],
    expected: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """交互要求 F 提示，收集要求对应容器，退出要求局内。"""
    flow = load_published_flow('janus_high_b')
    op = BagelRunFlow(MagicMock(), flow)
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, '_has', lambda name, screen_name='贝果-局内': name in areas)
    assert op.precondition(flow.steps[action_index]) == expected


@pytest.mark.parametrize('action', ['store', 'close', 'unlock'])
@pytest.mark.parametrize('areas,interrupted', [
    ({'按键-普通攻击'}, True),
    (set(), False),
    ({'按键-普通攻击', '搜查容器标题'}, False),
    ({'按键-普通攻击', '电子保险箱标题'}, False),
    ({'按键-普通攻击', '大保险解锁提示'}, False),
])
def test_failed_container_step_checks_new_frame(
    action: str, areas: set[str], interrupted: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只凭失败后的新画面分类中断；未知画面或面板仍在时保留原始错误。"""
    flow = load_published_flow('janus_high_a')
    step = next(s for s in flow.steps if s.action == action)
    op = BagelRunFlow(MagicMock(), flow, (step.id, 'exit'))
    monkeypatch.setattr(op, 'precondition', lambda _: None)
    fresh: set[str] = {'搜查容器标题'}
    monkeypatch.setattr(op, '_has', lambda area, screen_name='贝果-局内': area in fresh)

    def screenshot() -> None:
        """旧图仍在搜查；只有重新截图才能看到子操作结束画面。"""
        fresh.clear()
        fresh.update(areas)

    monkeypatch.setattr(op, 'screenshot', screenshot)
    child = MagicMock()
    child.execute.return_value = OperationResult(
        False, '原始子操作错误', BagelRecoverableFailure('原始子操作错误'),
    )
    monkeypatch.setattr(op, 'build_operation', lambda _: child)
    result = op.run_step()
    assert result.is_fail
    assert result.status == (BagelOperation.STATUS_INTERRUPTED if interrupted else '原始子操作错误')
    assert op.cursor == 0


def test_safe_attack_button_reaches_shared_executor(
    test_context: object, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """左侧文字不参与局内判断，普通攻击按钮与交互提示允许进入保险箱交互。"""
    flow = load_published_flow('janus_high_a')
    step = next(s for s in flow.steps if s.action == 'interact' and s.target == 'safe')
    op = BagelRunFlow(test_context, flow, (step.id,))
    test_context.mock_screen('贝果-局内', '电子保险箱交互-HUD错字-20260930')
    op.screenshot()
    assert op._has('按键-普通攻击', '战斗画面')
    child = MagicMock()
    child.execute.return_value = OperationResult(True, '已打开光圈解锁界面')
    monkeypatch.setattr(op, 'build_operation', lambda _: child)
    result = op.run_step()
    assert result.is_success, result.status
    child.execute.assert_called_once()


@pytest.mark.parametrize('action', ['store', 'close'])
@pytest.mark.parametrize('recovers', [False, True])
def test_search_label_gap_waits_at_step_boundary(
    test_context: object, monkeypatch: pytest.MonkeyPatch, action: str, recovers: bool,
) -> None:
    """真实漏字帧先等待；恢复才执行动作，持续漏字有界停止。"""
    flow = load_published_flow('janus_high_b')
    step = next(s for s in flow.steps if s.action == action)
    op = BagelRunFlow(test_context, flow, (step.id,))
    op.last_screenshot = cv2_utils.read_image(
        'zzz-od-test/screens/贝果-局内/武备箱安全箱文字漏识别-20260924.webp',
    )
    child = MagicMock()
    child.execute.return_value = OperationResult(True, '完成')
    build = MagicMock(return_value=child)
    monkeypatch.setattr(op, 'build_operation', build)
    for _ in range(5):
        assert op.run_step().result == OperationRoundResultEnum.WAIT
    build.assert_not_called()
    if recovers:
        test_context.mock_screen('贝果-局内', '武备箱搜查中-r07')
        op.screenshot()
        assert op.run_step().is_success
        child.execute.assert_called_once()
    else:
        assert op.run_step().is_fail
        build.assert_not_called()


def test_execute_advances_wait_nodes_and_releases(
    test_context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """完整执行框架推进 WAIT 步骤，终态清理输入，不接入仓库。"""
    controller = FixtureController(test_context)
    controller.set_phases([{'frame': ('贝果-局内', '高危A出生-原生1080')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    cleanup = MagicMock()
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.release_flow_inputs', cleanup)
    flow = load_published_flow('janus_high_a')
    seen = []
    op = BagelRunFlow(test_context, flow, ('open_box', 'store_box'))
    monkeypatch.setattr(op, 'precondition', lambda _: None)

    def build(step: object) -> object:
        seen.append(step.action)
        child = MagicMock()
        child.execute.return_value = OperationResult(True, '完成')
        return child

    monkeypatch.setattr(op, 'build_operation', build)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert seen == ['interact', 'store']
        cleanup.assert_called_with(test_context)
    finally:
        reset_running_state(test_context, op)
