from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_loadout import controller as controller
from test.harness.bagel_loadout import running_operation
from test.harness.fixture_controller import WatchdogOperationMixin

from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext
    from test.harness.bagel_loadout import TransferController


class WatchedEnter(WatchdogOperationMixin, BagelEnter):
    """执行真实节点图，给未知帧的时间上限留够观察轮数。"""

    watchdog_max_rounds: int = 120


def entry_prefix() -> list[dict]:
    """选择已正确，直接到零携带核对。"""
    return [
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '前往备战')},
        {'frame': ('贝果-备战', '高危零携带-原生1080'),
         'exit': ('on_click_in', '贝果-备战', '前往空洞')},
    ]


def entry_suffix() -> list[dict]:
    """零投资后必须看到局内画面。"""
    return [
        {'frame': ('贝果-入场确认', '高危零投资-原生1080'),
         'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞')},
        {'frame': ('贝果-局内', '高危A出生-原生1080')},
    ]


def click_count(ctx: TestContext, ctl: TransferController, screen: str, area: str) -> int:
    """只统计指定区域内的实际输入。"""
    rect = ctx.screen_loader.get_area(screen, area).pc_rect
    return sum(rect.x1 <= p.x <= rect.x2 and rect.y1 <= p.y <= rect.y2 for p in ctl.recorded_clicks)


@pytest.mark.parametrize('selection', ['correct', 'wrong_map', 'wrong_difficulty', 'delayed'])
def test_selection_verified_before_prepare(
    test_context: TestContext, controller: TransferController, selection: str,
) -> None:
    """完整入场核验正确免点击、错误纠正及慢更新时不连点。"""
    phases = entry_prefix()
    if selection in {'wrong_map', 'delayed'}:
        wrong = {'frame': ('贝果-选图', '城郊高危-20260926'),
                 'exit': ('on_click_in', '贝果-选图', '雅努斯')}
        phases.insert(0, wrong)
        if selection == 'delayed':
            phases.insert(1, {'frame': wrong['frame'], 'exit': ('on_polls', 4)})
    if selection == 'wrong_difficulty':
        phases.insert(0, {'frame': ('贝果-选图', '雅努斯困难-原生1080'),
                          'exit': ('on_click_in', '贝果-选图', '高危')})
    controller.set_phases(phases + entry_suffix())
    op = WatchedEnter(test_context)
    with running_operation(op):
        result = op.execute()
    assert result.success, result.status
    assert click_count(test_context, controller, '贝果-选图', '雅努斯') == int(selection in {'wrong_map', 'delayed'})
    assert click_count(test_context, controller, '贝果-选图', '高危') == int(selection == 'wrong_difficulty')


@pytest.mark.parametrize('area', ['选中地图', '推荐价值'])
def test_unknown_selection_stops_without_input(
    test_context: TestContext, controller: TransferController, area: str,
) -> None:
    """保留选图入口，只遮核验读数，不能猜测点击或进入备战。"""
    frame = test_context.load_screen('贝果-选图', '雅努斯高危-原生1080').copy()
    rect = test_context.screen_loader.get_area('贝果-选图', area).pc_rect
    frame[rect.y1:rect.y2, rect.x1:rect.x2] = 0
    controller.set_phases([{'frame': frame}])
    op = WatchedEnter(test_context)
    with running_operation(op):
        result = op.execute()
    assert not result.success
    assert '看门狗' not in result.status
    assert controller.recorded_clicks == []


@pytest.mark.parametrize('scenario,expected_clicks,success', [
    ('normal', 3, True), ('reordered', 3, True), ('delayed', 3, True),
    ('missed', 4, True), ('stuck', 2, False), ('unknown', 0, False),
    ('reappeared', 2, False), ('blank', 1, False),
])
def test_warning_transitions_have_bounded_inputs(
    test_context: TestContext, controller: TransferController,
    scenario: str, expected_clicks: int, success: bool,
) -> None:
    """运行完整入场图，用实际提示帧验证逐弹窗核验与一次补点上限。"""
    warnings = [
        {'frame': ('贝果-入场确认', state),
         'exit': ('on_click_in', '贝果-入场确认', '确认')}
        for state in ('高危零装备价值-原生1080', '未装备武备-原生1080', '未穿戴队伍装备-原生1080')
    ]
    if scenario == 'reordered':
        warnings.reverse()
    elif scenario == 'delayed':
        warnings.insert(1, {'frame': warnings[0]['frame'], 'exit': ('on_polls', 4)})
    elif scenario == 'missed':
        warnings.insert(1, warnings[0].copy())
    elif scenario == 'stuck':
        warnings = [{'frame': warnings[0]['frame']}]
    elif scenario == 'unknown':
        warnings = [{'frame': ('贝果-退出确认', '主动退出-原生1080')}]
    elif scenario == 'reappeared':
        warnings = [warnings[0], warnings[1], warnings[0]]
    elif scenario == 'blank':
        warnings = [warnings[0], {'frame': ('贝果-局内', '加载-原生1080')}]
    controller.set_phases(entry_prefix() + warnings + entry_suffix())
    op = WatchedEnter(test_context)
    with running_operation(op):
        result = op.execute()
    assert result.success == success, result.status
    assert '看门狗' not in result.status
    assert click_count(test_context, controller, '贝果-入场确认', '确认') == expected_clicks
    assert controller.click_hit_area('贝果-入场确认', '零投资前往空洞') == success


def test_reused_operation_rechecks_map(
    test_context: TestContext, controller: TransferController,
) -> None:
    """同一实例再次执行也不沿用上局地图核验与弹窗状态。"""
    op = WatchedEnter(test_context)
    for wrong in (False, True):
        phases = entry_prefix()
        if wrong:
            phases.insert(0, {'frame': ('贝果-选图', '城郊高危-20260926'),
                              'exit': ('on_click_in', '贝果-选图', '雅努斯')})
        controller.set_phases(phases + entry_suffix())
        with running_operation(op):
            result = op.execute()
        assert result.success, result.status
        assert controller.click_hit_area('贝果-选图', '雅努斯') == wrong


def test_pause_at_prepare_returns_to_selection(
    test_context: TestContext, controller: TransferController, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """备战时暂停模拟用户换图，恢复后必须返回核验，不沿用原资格。"""
    phases = entry_prefix()
    phases[1] = {'frame': ('贝果-备战', '高危零携带-原生1080'),
                 'exit': ('on_click_in', '菜单', '返回')}
    phases += [
        {'frame': ('贝果-选图', '城郊高危-20260926'),
         'exit': ('on_click_in', '贝果-选图', '雅努斯')},
        *entry_prefix(), *entry_suffix(),
    ]
    controller.set_phases(phases)
    op = WatchedEnter(test_context)
    screenshot = controller.screenshot
    paused = False

    def pause_once(independent: bool = False) -> tuple:
        """只在已到备战时触发真实操作的暂停处理。"""
        nonlocal paused
        if controller.phase_idx == 1 and not paused:
            paused = True
            op.handle_pause()
        return screenshot(independent)

    monkeypatch.setattr(controller, 'screenshot', pause_once)
    with running_operation(op):
        result = op.execute()
    assert result.success, result.status
    assert controller.click_hit_area('菜单', '返回')
    assert controller.click_hit_area('贝果-选图', '雅努斯')


def test_pause_during_confirmation_does_not_reuse_qualification(test_context: TestContext) -> None:
    """确认阶段暂停后撤销零携带资格，禁止继续自动确认。"""
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.handle_pause()
    result = op.confirm_entry()
    assert result.is_fail
    assert '暂停后需重新核对' in result.status


@pytest.mark.parametrize('state,expected', [
    ('城郊高危-20260926', '重新核对选图'),
    ('雅努斯困难-原生1080', '重新核对选图'),
])
def test_selection_changed_before_prepare_is_rechecked(
    test_context: TestContext, state: str, expected: str,
) -> None:
    """两节点间地图或难度变更时返回核验，不能沿用上一帧直接点备战。"""
    test_context.mock_screen('贝果-选图', state)
    op = BagelEnter(test_context)
    op.screenshot()
    assert op.open_prepare().status == expected
