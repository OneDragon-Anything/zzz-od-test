"""容器阶段切换与子操作无限等待的完整执行边界。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_container import (
    WatchedFlow,
    WatchedOpenBox,
    execute,
    phases,
    prepare,
)

from zzz_od.application.bagel.bagel_container import ContainerRecovery
from zzz_od.application.bagel.bagel_flow import load_published_flow

if TYPE_CHECKING:
    from test.conftest import TestContext

    from zzz_od.application.bagel.bagel_flow import BagelFlow

pytestmark = pytest.mark.usefixtures('no_round_wait')


def repeat_box(flow: BagelFlow) -> BagelFlow:
    """复用发布步骤创建两个武备箱阶段，仅改变第二组步骤 ID。"""
    group = tuple(s for s in flow.steps if s.target == 'box' and s.action != 'move')
    end = flow.steps.index(group[-1]) + 1
    return replace(flow, steps=(
        *flow.steps[:end], *(replace(s, id=f'{s.id}_second') for s in group), *flow.steps[end:],
    ))


@pytest.mark.parametrize(
    'next_target',
    [
        'box',
    ],
)
def test_next_approach_has_own_time_budget(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, next_target: str,
) -> None:
    """前一阶段在上限前完成，步骤间等待越过旧上限也不能阻止新阶段。"""
    prompt, _, _ = phases('box')
    controller, prepared, events = prepare(test_context, monkeypatch, 'box', [prompt])
    flow = repeat_box(prepared.flow) if next_target == 'box' else load_published_flow('janus_high_a')
    approaches = tuple(s for s in flow.steps if s.action == 'approach')
    first_frame = '白鸽工地箱前-录像8s' if next_target == 'box' else '雅努斯箱前-r07-32s'
    second_frame = first_frame if next_target == 'box' else '电子保险箱F提示'
    controller.set_phases([
        {'frame': ('贝果-局内', first_frame)}, {'frame': ('贝果-局内', second_frame)},
    ])
    op = WatchedFlow(test_context, flow, tuple(s.id for s in approaches))

    def next_container(event: dict[str, object]) -> None:
        """推进到另一容器的存档，并把前一阶段有效耗时置于上限前。"""
        events.append(event)
        if event['kind'] == 'done' and event['step_id'] == approaches[0].id:
            budget = op._container_recovery
            assert budget is not None and budget.started_at is not None
            op.operation_start_time -= 29.95 - (op.operation_usage_time - budget.started_at)
            controller._advance_phase()

    op.on_event = next_container
    result = execute(op)
    assert result.success, (result.status, result.data)
    assert [e['step_id'] for e in events if e['kind'] == 'done'] == [s.id for s in approaches]
    assert not [e for e in controller.trace if e[0] in ('w', 'turn', 'f')]


def test_child_watchdog_stops_wait_when_business_timeout_is_disabled(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """故意关闭业务时限，验证等待子操作仍由测试看门狗停止。"""
    prompt, _, _ = phases('box')
    controller, op, _ = prepare(test_context, monkeypatch, 'box', [
        {**prompt, 'on': 'f'}, {**prompt, 'hide': ('交互提示', '按键-普通攻击')},
    ])
    monkeypatch.setattr(ContainerRecovery, 'error', lambda _: None)
    monkeypatch.setattr(WatchedOpenBox, 'watchdog_max_rounds', 5)
    result = execute(op)
    assert not result.success and '看门狗' in str(result.status)
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['f']
    assert controller.frames < 20
