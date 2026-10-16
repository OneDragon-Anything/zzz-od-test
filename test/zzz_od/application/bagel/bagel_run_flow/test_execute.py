"""公共执行器的勾选顺序、前置画面及失败状态。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

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
    pass

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.mark.parametrize(
    'failed_status',
    [
        '未打开容器',
        BagelOperation.STATUS_INTERRUPTED,
    ],
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


@pytest.mark.parametrize(
    'areas,interrupted,action',
    [
        ({'按键-普通攻击'}, True, 'store'),
        (set(), False, 'close'),
        ({'按键-普通攻击', '搜查容器标题'}, False, 'unlock'),
        ({'按键-普通攻击', '电子保险箱标题'}, False, 'store'),
        ({'按键-普通攻击', '大保险解锁提示'}, False, 'close'),
    ],
)
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


@pytest.mark.parametrize(
    'recovers,action',
    [
        (False, 'store'),
        (True, 'close'),
    ],
)
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
