"""正式执行器通过真实截图定位，丢图时松键，恢复或持续失败时正确收尾。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow

if TYPE_CHECKING:
    import numpy as np
    from test.conftest import TestContext


class ReplayController(FixtureController):
    """转向后进入缺图帧；只记录输入，不连接游戏。"""

    def __init__(self, ctx: TestContext) -> None:
        """记录缺图期间是否松键。"""
        super().__init__(ctx)
        self.releases: int = 0

    @property
    def current_frame(self) -> np.ndarray:
        """保留真实 HUD，仅将缺图阶段的小地图遮黑。"""
        image = super().current_frame.copy()
        if self.phase_idx == 1:
            image[206:407, 1533:1734] = 0
        return image

    def turn_by_angle_diff(self, angle_diff: float) -> None:
        """真实算法要求转向时，测试剧本进入下一帧。"""
        self.recorded_inputs.append('turn')
        self._advance_phase()

    def stop_moving_forward(self) -> None:
        """记录松键，不产生桌面输入。"""
        self.releases += 1

    def start_moving_forward(self) -> None:
        """测试路线不应在缺图时要求持续前进。"""
        self.recorded_inputs.append('hold')

    def move_w(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """记录短步，不产生桌面输入。"""
        self.recorded_inputs.append('w')


class WatchedNavigate(WatchdogOperationMixin, BagelNavigate):
    """限定离线剧本轮数，避免失败时无限等待。"""

    watchdog_max_rounds: int = 12


@pytest.mark.usefixtures('no_round_wait')
@pytest.mark.parametrize('recover', [True, False])
def test_formal_executor_recovers_or_stops_after_map_loss(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, recover: bool,
) -> None:
    """正式派发子导航，定位不打桩；成功和失败均松键并释放执行器输入。"""
    controller = ReplayController(test_context)
    missing = {'frame': ('贝果-局内', '雅努斯出生-r01-39s')}
    if recover:
        missing['exit'] = ('on_polls', 1)
    controller.set_phases([
        {'frame': ('贝果-局内', '雅努斯出生-r01-39s')},
        missing,
        {'frame': ('贝果-局内', '雅努斯箱前-r07-32s')},
    ])
    monkeypatch.setattr(test_context, 'controller', controller)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.BagelNavigate', WatchedNavigate)
    cleanup = MagicMock()
    monkeypatch.setattr('zzz_od.application.bagel.bagel_run_flow.release_flow_inputs', cleanup)
    flow = load_published_flow('janus_high_a')
    step = next(item for item in flow.steps if item.action == 'approach' and item.target == 'box')
    events: list[dict[str, object]] = []
    operation = BagelRunFlow(test_context, flow, (step.id,), on_event=events.append)
    enter_running_state(test_context)
    try:
        result = operation.execute()
        assert result.success is recover, result.status
        observations = [event for event in events if event['kind'] == 'observation']
        assert any(event['position'] is None for event in observations)
        assert any(event['position'] is not None for event in observations)
        assert controller.releases > 0
        assert controller.recorded_inputs == ['turn']
        cleanup.assert_called_with(test_context)
        assert events[-1]['kind'] == 'finished'
    finally:
        reset_running_state(test_context, operation)
