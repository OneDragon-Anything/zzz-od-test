from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import (
    WatchedClear,
    detail_frame,
    paint_count,
    running_operation,
    unload_frames,
)
from test.harness.bagel_loadout import controller as controller

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_clear_loadout import (
    LOADOUT_CENTERS,
)

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


def test_confirmed_unload_selects_next_from_same_observation(
    test_context: TestContext, controller: TransferController,
) -> None:
    """已用两帧确认卸装后，直接从该帧选下一格，不额外等待两轮。"""
    frames = unload_frames(test_context)
    controller.set_phases([{'frame': frames[1], 'exit': ('transfer', LOADOUT_CENTERS[1])}])
    op = WatchedClear(test_context)
    op.pending = True
    op.pending_center = LOADOUT_CENTERS[0]
    op.pending_group = '武备价值'
    op.before_values = {'武备价值': '270000', '装备价值': '160000', '道具价值': '78000',
                        '背包数量': '0/50', '安全箱数量': '0/5'}
    op.pending_started = time.monotonic()
    with running_operation(op):
        op.last_screenshot = frames[1]
        assert op.unload_next().status == '等待卸装结果稳定'
        op.last_screenshot = frames[1].copy()
        assert op.unload_next().status == '等待武备第 2 格双击转入仓库'
        assert op.moved == 1
        assert len(controller.recorded_clicks) == 2


@pytest.mark.parametrize('kind', ['unchanged', 'detail', 'wrong_value', 'wrong_container'])
def test_double_click_unconfirmed_result_stops_after_allowed_retry(
    test_context: TestContext, controller: TransferController, kind: str,
) -> None:
    """无变化只重试一次；停在详情或去向异常不重试。"""
    frames = unload_frames(test_context)
    before, after = frames[-2], frames[-1].copy()
    source = LOADOUT_CENTERS[-1]
    if kind == 'unchanged':
        after = before
    elif kind == 'detail':
        after = detail_frame(test_context, before, source)
    elif kind == 'wrong_value':
        paint_count(test_context, after, '贝果-备战', '道具价值', '3000')
    else:
        paint_count(test_context, after, '贝果-备战', '背包数量', '1/20')
    phases = [{'frame': before, 'exit': ('transfer', source)}]
    if kind == 'unchanged':
        phases.append({'frame': after, 'exit': ('transfer', source)})
    phases.append({'frame': after})
    controller.set_phases(phases)
    op = WatchedClear(test_context)
    with running_operation(op):
        for _ in range(30):
            op.screenshot()
            result = op.unload_next()
            if result.is_fail:
                break
        assert result.is_fail, result.status
        assert len(controller.recorded_clicks) == (4 if kind == 'unchanged' else 2)
        assert all(pos.tuple() == source.tuple() for pos in controller.recorded_clicks)
        assert op.moved == 0


def test_each_slot_can_retry_once_after_confirmed_no_change(
    test_context: TestContext, controller: TransferController,
) -> None:
    """两件道具均首次双击未生效、重试成功，各自只有一次重试额度。"""
    frames = unload_frames(test_context)
    phases: list[dict] = []
    for index in (-3, -2):
        source = LOADOUT_CENTERS[index + 1]
        phases.extend([
            {'frame': frames[index], 'exit': ('transfer', source)},
            {'frame': frames[index], 'exit': ('transfer', source)},
        ])
    phases.append({'frame': frames[-1]})
    controller.set_phases(phases)
    op = WatchedClear(test_context)
    with running_operation(op):
        for _ in range(40):
            op.screenshot()
            result = op.unload_next()
            if result.is_success or result.is_fail:
                break
        assert result.is_success, result.status
        assert op.moved == 2
        assert len(controller.recorded_clicks) == 8


def test_double_click_then_pause_only_verifies_result(
    test_context: TestContext, controller: TransferController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双击完成后暂停恢复只核验卸装结果，不重复发送双击。"""
    frames = unload_frames(test_context)
    source = LOADOUT_CENTERS[-1]
    controller.set_phases([{'frame': frames[-2], 'exit': ('transfer', source)}, {'frame': frames[-1]}])
    op = WatchedClear(test_context)
    original = controller.click

    def click(pos: Point, press_time: float = 0, **kwargs: object) -> bool:
        result = original(pos, press_time, **kwargs)
        if len(controller.recorded_clicks) == 2:
            op.handle_pause()
            op.handle_resume()
        return result

    monkeypatch.setattr(controller, 'click', click)
    with running_operation(op):
        for _ in range(5):
            op.screenshot()
            result = op.unload_next()
            if result.is_success:
                break
        assert result.is_success, result.status
        assert op.moved == 1
        assert len(controller.recorded_clicks) == 2


def test_pause_after_double_click_disables_retry(
    test_context: TestContext, controller: TransferController,
) -> None:
    """双击后暂停过，即使画面未变也不重发输入。"""
    before = unload_frames(test_context)[-2]
    source = LOADOUT_CENTERS[-1]
    controller.set_phases([{'frame': before, 'exit': ('transfer', source)}, {'frame': before}])
    op = WatchedClear(test_context)
    with running_operation(op):
        op.screenshot()
        op.unload_next()
        op.screenshot()
        assert '双击转入仓库' in op.unload_next().status
        op.handle_pause()
        op.handle_resume()
        for _ in range(15):
            op.screenshot()
            result = op.unload_next()
            if result.is_fail:
                break
        assert result.is_fail, result.status
        assert len(controller.recorded_clicks) == 2
        assert op.moved == 0


@pytest.mark.parametrize('animated_slot', [0, 2])
def test_empty_slot_animation_does_not_block_completed_unload(
    test_context: TestContext, controller: TransferController, animated_slot: int,
) -> None:
    """第二件已转存，其他空槽或有物槽的图标变化不能阻止确认。"""
    after = test_context.load_screen('贝果-备战', 'clear_loadout_second_weapon_stored')
    previous = after.copy()
    state = 'clear_loadout_empty' if animated_slot == 0 else 'clear_loadout_carried'
    alternate = test_context.load_screen('贝果-备战', state)
    # 明确合成同一槽位的另一种图标外观，其余像素和五项读数保留现场。
    x, y = LOADOUT_CENTERS[animated_slot].tuple()
    previous[y-32:y+32, x-32:x+32] = alternate[y-32:y+32, x-32:x+32]
    controller.set_phases([{'frame': after}])
    op = WatchedClear(test_context)
    op.pending = True
    op.pending_center = LOADOUT_CENTERS[1]
    op.pending_group = '武备价值'
    op.before_values = {'武备价值': '180000', '装备价值': '160000', '道具价值': '78000',
                        '背包数量': '0/50', '安全箱数量': '0/5'}
    op.pending_started = time.monotonic()
    op.moved = 1
    op.last_screenshot = previous
    assert op.unload_next().status == '等待卸装结果稳定'
    op.last_screenshot = after
    assert not op.unload_next().is_fail
    assert op.moved == 2
    assert not controller.recorded_clicks
    inspect = WatchedClear(test_context)
    inspect.last_screenshot = previous
    assert inspect.inspect_loadout().status == '等待备战格子稳定'
    inspect.last_screenshot = after
    assert inspect.inspect_loadout().status == '背包安全箱已空'


@pytest.mark.parametrize('change', ['value', 'occupied', 'unknown'])
def test_unload_still_rejects_unstable_or_unknown_observation(
    test_context: TestContext, controller: TransferController, change: str,
) -> None:
    """图标动画可忽略，但读数、占用变化或未知槽位仍不得报告转存完成。"""
    after = test_context.load_screen('贝果-备战', 'clear_loadout_second_weapon_stored')
    previous = after.copy()
    if change == 'value':
        paint_count(test_context, previous, '贝果-备战', '武备价值', '180000')
    else:
        x, y = LOADOUT_CENTERS[1].tuple()
        if change == 'unknown':
            previous[y-32:y+32, x-32:x+32] = 0
        else:
            carried = test_context.load_screen('贝果-备战', 'clear_loadout_carried')
            previous[y-32:y+32, x-32:x+32] = carried[y-32:y+32, x-32:x+32]
    controller.set_phases([{'frame': after}])
    op = WatchedClear(test_context)
    op.pending = True
    op.pending_center = LOADOUT_CENTERS[1]
    op.pending_group = '武备价值'
    op.before_values = {'武备价值': '180000', '装备价值': '160000', '道具价值': '78000',
                        '背包数量': '0/50', '安全箱数量': '0/5'}
    op.pending_started = time.monotonic()
    op.last_screenshot = after
    assert op.unload_next().status == '等待卸装结果稳定'
    op.last_screenshot = previous
    assert not op.unload_next().is_success
    op.last_screenshot = after
    assert op.unload_next().status == '等待卸装结果稳定'
    assert op.moved == 0
    assert not controller.recorded_clicks
