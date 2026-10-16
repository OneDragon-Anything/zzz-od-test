from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.bagel_warehouse import _clean_phases
from test.harness.fixture_controller import WatchdogOperationMixin

from zzz_od.application.bagel.bagel_clean import FILTER_TICKS, BagelCleanWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


class WatchedClean(WatchdogOperationMixin, BagelCleanWarehouse):
    """执行真实清理节点，给等待超时留出有限轮数。"""

    watchdog_max_rounds: int = 100


@pytest.mark.parametrize(
    'scenario',
    [
        'delayed',
        'stuck',
    ],
)
def test_filter_click_waits_for_target_state(
    test_context: TestContext,
    controller: TransferController,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    """点击后的旧帧或模糊帧只观察，不二次翻转；未生效则不出售。"""
    phases = _clean_phases('确认出售')
    old_frame = test_context.load_screen(*phases[2]['frame']).copy()
    if scenario == 'unclear':
        rect = test_context.screen_loader.get_area('贝果-仓库', FILTER_TICKS[0]).pc_rect
        old_frame[rect.y1 : rect.y2, rect.x1 : rect.x2] = 0
        old_frame[rect.y1 : rect.y1 + (rect.y2 - rect.y1) // 8, rect.x1 : rect.x2] = (
            0,
            145,
            255,
        )
    delayed: dict = {'frame': old_frame}
    if scenario in {'delayed', 'paused'}:
        delayed['exit'] = ('on_polls', 4)
    phases.insert(3, delayed)
    controller.set_phases(phases)
    op = WatchedClean(test_context)
    counts = iter([280, 279])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    screenshot = controller.screenshot

    def pause_before_observation(independent: bool = False) -> tuple:
        """暂停后仍用新帧确认刚点击选项，不重置为可再次点击。"""
        if controller.phase_idx == 3:
            op.handle_pause()
        return screenshot(independent)

    if scenario == 'paused':
        monkeypatch.setattr(controller, 'screenshot', pause_before_observation)
    with running_operation(op):
        result = op.execute()
    assert result.success == (scenario in {'delayed', 'paused'}), result.status
    assert '看门狗' not in result.status
    rect = test_context.screen_loader.get_area('贝果-仓库', FILTER_TICKS[0]).pc_rect
    clicks = [
        p
        for p in controller.recorded_clicks
        if rect.x1 <= p.x <= rect.x2 and rect.y1 <= p.y <= rect.y2
    ]
    assert len(clicks) == 1
    if not result.success:
        assert '点击后未能核对目标状态' in result.status
        assert not controller.click_hit_area('贝果-仓库', '筛选确认')
        assert not controller.click_hit_area('贝果-仓库', '出售弹窗确认')


@pytest.mark.parametrize(
    'stuck',
    [
        True,
    ],
)
def test_reward_confirmation_is_not_repeated(
    test_context: TestContext,
    controller: TransferController,
    monkeypatch: pytest.MonkeyPatch,
    stuck: bool,
) -> None:
    """获得提示慢消失时只点击一次，持续不变也必须有限停止。"""
    phases = _clean_phases('确认出售')
    reward = {'frame': ('贝果-仓库', '出售获得硬币-20260921')}
    if not stuck:
        reward['exit'] = ('on_polls', 4)
    phases.insert(-1, reward)
    controller.set_phases(phases)
    op = WatchedClean(test_context)
    counts = iter([280, 279])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    with running_operation(op):
        result = op.execute()
    assert result.success != stuck, result.status
    assert '看门狗' not in result.status
    rect = test_context.screen_loader.get_area('贝果-仓库', '出售获得确认').pc_rect
    # 出售预览确认位于不同区域，核对实际奖励区域点击次数。
    clicks = [
        p
        for p in controller.recorded_clicks
        if rect.x1 <= p.x <= rect.x2 and rect.y1 <= p.y <= rect.y2
    ]
    assert len(clicks) == 1
