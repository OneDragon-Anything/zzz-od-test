from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.fixture_controller import WatchdogOperationMixin

from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_investment import read_investment

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController

    from one_dragon.base.geometry.point import Point


class WatchedEnter(WatchdogOperationMixin, BagelEnter):
    """使用完整入场节点图，避免等待分支回归后无限循环。"""

    watchdog_max_rounds: int = 35


def investment_frame(ctx: TestContext, amount: str) -> MatLike:
    """500K 使用实际截图，其余金额合成；帧间转换仅用于离线测试。"""
    if amount == '500K':
        return ctx.load_screen('贝果-入场确认', '高危投资500K-原生1080').copy()
    frame = ctx.load_screen('贝果-入场确认', '高危零投资-原生1080').copy()
    coin = frame[700:754, 927:966].copy()
    cv2.rectangle(frame, (780, 700), (1139, 753), (28, 28, 28), -1)
    frame[700:754, 780:819] = coin
    if amount:
        cv2.putText(frame, amount, (825, 740), cv2.FONT_HERSHEY_SIMPLEX,
                    1.1, (255, 255, 255), 2, cv2.LINE_AA)
    return frame


def entry_phases() -> list[dict]:
    """从选图开始，经过难度、零携带与三类确认后到投资页。"""
    return [
        {'frame': ('贝果-选图', '雅努斯困难-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '雅努斯')},
        {'frame': ('贝果-选图', '雅努斯困难-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '高危')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '前往备战')},
        {'frame': ('贝果-备战', '高危零携带-原生1080'),
         'exit': ('on_click_in', '贝果-备战', '前往空洞')},
        *[{'frame': ('贝果-入场确认', state),
           'exit': ('on_click_in', '贝果-入场确认', '确认')}
          for state in ('高危零装备价值-原生1080', '未装备武备-原生1080', '未穿戴队伍装备-原生1080')],
    ]


@pytest.mark.parametrize('amount, delayed', [
    ('0', False), ('500000', False), ('1000000', True), ('500K', False), ('1.5M', True), ('', False),
])
def test_investment_rechecked_before_entry(
    test_context: TestContext, controller: TransferController,
    amount: str, delayed: bool,
) -> None:
    """全流程覆盖初始为零、非零归零、更新延迟以及 OCR 暂缺后恢复。"""
    phases = entry_phases()
    before = investment_frame(test_context, amount)
    assert read_investment(test_context, before) == amount
    if amount != '0':
        if amount:
            phases.append({'frame': before, 'exit': ('on_click_in', '贝果-入场确认', '投资最小值')})
        if delayed or not amount:
            phases.append({'frame': before, 'exit': ('on_polls', 1)})
    phases.extend([
        {'frame': ('贝果-入场确认', '高危零投资-原生1080'),
         'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞')},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ])
    controller.set_phases(phases)
    op = WatchedEnter(test_context)
    with running_operation(op):
        result = op.execute()
    assert result.success, result.status
    assert result.status == '已进入雅努斯高危'
    assert controller.phase_idx == len(phases) - 1
    assert op.zero_checked and op.investment_confirmed
    assert controller.click_hit_area('贝果-入场确认', '投资最小值') == bool(amount and amount != '0')
    assert len(controller.recorded_clicks) == 8 + (1 + int(delayed) if amount and amount != '0' else 0)


@pytest.mark.parametrize('failure', ['click_failed', 'unchanged', 'unclear', 'min_missing', 'unclear_after_min', 'alternating'])
def test_investment_failure_stops_and_preserves_frame(
    test_context: TestContext, controller: TransferController,
    monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    """MIN 失败、无变化及识别不明均限次停在投资页并保存原帧，不进入空洞。"""
    phases = entry_phases()
    before = investment_frame(test_context, '500K')
    unclear = investment_frame(test_context, '')
    if failure in {'unclear_after_min', 'alternating'}:
        phases.append({'frame': before, 'exit': ('on_click_in', '贝果-入场确认', '投资最小值')})
    if failure == 'alternating':
        phases.extend([
            {'frame': unclear, 'exit': ('on_polls', 1)},
            {'frame': before, 'exit': ('on_click_in', '贝果-入场确认', '投资最小值')},
        ])
    final = unclear if failure in {'unclear', 'unclear_after_min', 'alternating'} else before
    if failure == 'min_missing':
        cv2.rectangle(final, (420, 775), (549, 904), (28, 28, 28), -1)
    phases.append({'frame': final})
    controller.set_phases(phases)
    min_rect = test_context.screen_loader.get_area('贝果-入场确认', '投资最小值').pc_rect
    original_click = controller.click
    if failure == 'click_failed':
        def failed_click(
            pos: Point | None = None, press_time: float = 0,
            pc_alt: bool = False, gamepad_key: str | None = None,
        ) -> bool:
            """只让投资 MIN 点击失败，其余入场动作保留真实流程。"""
            result = original_click(pos, press_time, pc_alt, gamepad_key)
            in_min = (pos is not None and min_rect.x1 <= pos.x <= min_rect.x2
                      and min_rect.y1 <= pos.y <= min_rect.y2)
            return False if in_min else result

        monkeypatch.setattr(controller, 'click', failed_click)
    op = WatchedEnter(test_context)
    saved = MagicMock(return_value='投资失败现场.png')
    monkeypatch.setattr(op, 'save_screenshot', saved)
    with running_operation(op):
        result = op.execute()
    assert not result.success
    assert result.status == '无法确认零投资，停止并保留现场'
    assert controller.phase_idx == len(phases) - 1
    assert op.investment_retries == 3
    assert not op.investment_confirmed
    assert not controller.click_hit_area('贝果-入场确认', '零投资前往空洞')
    expected_clicks = {'click_failed': 3, 'unchanged': 3, 'unclear': 0, 'min_missing': 0,
                       'unclear_after_min': 1, 'alternating': 2}
    assert len(controller.recorded_clicks) == 7 + expected_clicks[failure]
    assert np.array_equal(op.last_screenshot, final)
    saved.assert_called_once()
