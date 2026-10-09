from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_clean import FILTER_TICKS, BagelCleanWarehouse
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_screen import parse_filter_count, read_area
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext

class WatchedClean(WatchdogOperationMixin, BagelCleanWarehouse):
    """限制清理轮数。"""

    watchdog_max_rounds: int = 40


class WatchedSettle(WatchdogOperationMixin, BagelSettleWarehouse):
    """限制结算编排轮数。"""

    watchdog_max_rounds: int = 20


@pytest.fixture
def controller(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """真截图与 OCR，点击按剧本推进。"""
    result = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', result)
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda _: None)
    return result


def test_unselected_icon_tint_is_not_ambiguous(test_context: TestContext) -> None:
    """门禁卡图标带少量蓝像素时仍判未选中，不把整组筛选当成看不清。"""
    import numpy as np

    op = BagelCleanWarehouse(test_context)
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    names = (
        '筛选-全部', '筛选-战术道具', '筛选-装备', '筛选-门禁卡', '筛选-Z',
        '筛选-贵重物品', '筛选-战术棱镜', '筛选-其他',
        '筛选-C', '筛选-B', '筛选-A', '筛选-S',
    )
    for name in names:
        area = test_context.screen_loader.get_area('贝果-仓库', name)
        assert area is not None
        rect = area.pc_rect
        crop = screen[rect.y1:rect.y2, rect.x1:rect.x2]
        if name == '筛选-贵重物品':
            crop[: crop.shape[0] // 2] = (0, 145, 255)
        elif name == '筛选-门禁卡':
            count = max(1, int(crop.shape[0] * crop.shape[1] * 0.025))
            rows, columns = np.unravel_index(np.arange(count), crop.shape[:2])
            crop[rows, columns] = (0, 145, 255)
            assert np.count_nonzero(np.all(crop == (0, 145, 255), axis=2)) == count
    op.last_screenshot = screen
    states = op._filter_states()
    assert states is not None
    assert states['筛选-贵重物品'] is True
    assert states['筛选-门禁卡'] is False
    assert states['筛选-全部'] is False


def test_custom_filter_checks_all_options(test_context: TestContext) -> None:
    """自定义勾装备与 Z 时，其它品质、类型及「全部」都应取消。"""
    op = BagelCleanWarehouse(test_context, ('筛选-装备', '筛选-Z'))
    test_context.mock_screen('贝果-仓库', '仓库快速选择')
    op.screenshot()
    states = op._filter_states()
    assert states is not None
    assert set(states) == {'筛选-全部', *FILTER_TICKS, '筛选-Z', '筛选-装备', '筛选-战术道具', '筛选-门禁卡'}
    assert set(op.filter_areas) == {'筛选-装备', '筛选-Z'}
    assert '筛选-全部' not in op.filter_areas


def test_custom_filter_rejects_all(test_context: TestContext) -> None:
    """任何配置都不能把「全部」送进出售筛选。"""
    with pytest.raises(ValueError):
        BagelCleanWarehouse(test_context, ('筛选-全部',))


def _clean_phases(sell_area: str) -> list[dict]:
    """从仓库主界面走到快速选择，再按 0 件或有件分流。"""
    phases: list[dict] = [
        {'frame': ('贝果-仓库', '空局仓库-原生1080'),
         'exit': ('on_click_in', '贝果-仓库', '批量出售')},
        {'frame': ('贝果-仓库', '仓库批量出售中'),
         'exit': ('on_click_in', '贝果-仓库', '批量选择')},
    ]
    for index, name in enumerate(FILTER_TICKS):
        phases.append({
            'frame': ('贝果-仓库', f'快速选择-步骤{index}-20260921'),
            'exit': ('on_click_in', '贝果-仓库', name),
        })
    phases.append({
        'frame': ('贝果-仓库', '快速选择-步骤7-20260921'),
        'exit': ('on_click_in', '贝果-仓库', '筛选确认'),
    })
    phases.append({
        'frame': ('贝果-仓库', '仓库批量出售中'),
        'exit': ('on_click_in', '贝果-仓库', sell_area),
    })
    if sell_area == '确认出售':
        phases.append({
            'frame': ('贝果-仓库', '出售二次确认-20260921'),
            'exit': ('on_click_in', '贝果-仓库', '出售弹窗确认'),
        })
        phases.append({
            'frame': ('贝果-仓库', '出售获得硬币-20260921'),
            'exit': ('on_click_in', '贝果-仓库', '出售获得确认'),
        })
    phases.append({'frame': ('贝果-仓库', '空局仓库-原生1080')})
    return phases


def test_idle_and_sell_mode_areas(test_context: TestContext) -> None:
    """主界面和出售底栏要用不同文字区分，不能共用「出售」。"""
    idle = BagelCleanWarehouse(test_context)
    test_context.mock_screen('贝果-仓库', '空局仓库-原生1080')
    idle.screenshot()
    assert idle._warehouse_idle()
    assert not idle._in_sell_mode()
    assert not idle._in_filter()

    selling = BagelCleanWarehouse(test_context)
    test_context.mock_screen('贝果-仓库', '仓库批量出售中')
    selling.screenshot()
    assert selling._in_sell_mode()
    assert not selling._warehouse_idle()
    assert not selling._in_filter()


def test_filter_dialog_areas_and_zero_count(test_context: TestContext) -> None:
    """快速选择截图要能点到写死勾选项，并读出 0 件。"""
    op = BagelCleanWarehouse(test_context)
    test_context.mock_screen('贝果-仓库', '仓库快速选择')
    op.screenshot()
    assert op._in_filter()
    for name in (*FILTER_TICKS, '快速选择标题', '筛选确认'):
        assert op._has_area(name), name
    text = read_area(test_context, op.last_screenshot, '贝果-仓库', '筛选数量')
    assert parse_filter_count(text) == 0, text


def test_clean_zero_count_cancels_without_selling(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """筛选 0 件时确认筛选后取消出售，不能点确认出售。"""
    controller.set_phases(_clean_phases('取消出售'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_clean.parse_filter_count', lambda _text: 0)
    op = WatchedClean(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelCleanWarehouse.STATUS_SKIPPED
        for name in ('批量出售', '批量选择', '筛选确认', *FILTER_TICKS):
            assert controller.click_hit_area('贝果-仓库', name), name
        assert not controller.click_hit_area('贝果-仓库', '确认出售')
        last = controller.recorded_clicks[-1]
        cancel = test_context.screen_loader.get_area('贝果-仓库', '取消出售').pc_rect
        assert cancel.x1 <= last.x <= cancel.x2 and cancel.y1 <= last.y <= cancel.y2
    finally:
        reset_running_state(test_context, op)


def test_clean_positive_count_confirms_sell(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有待出售件数时点确认出售，不取消。"""
    controller.set_phases(_clean_phases('确认出售'))
    op = WatchedClean(test_context)
    counts = iter([280, 279])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelCleanWarehouse.STATUS_DONE
        assert controller.click_hit_area('贝果-仓库', '确认出售')
        last = controller.recorded_clicks[-1]
        assert controller.click_hit_area('贝果-仓库', '出售弹窗确认')
        confirm = test_context.screen_loader.get_area('贝果-仓库', '出售获得确认').pc_rect
        assert confirm.x1 <= last.x <= confirm.x2 and confirm.y1 <= last.y <= confirm.y2
    finally:
        reset_running_state(test_context, op)


def _patch_settle_ops(
    monkeypatch: pytest.MonkeyPatch,
    deposit_statuses: list[str],
    clean_status: str = BagelCleanWarehouse.STATUS_DONE,
) -> list[str]:
    """按预定状态替换入仓和清理，记录调用顺序。"""
    events: list[str] = []
    deposits = list(deposit_statuses)

    def deposit_exec(self: BagelDeposit) -> OperationResult:
        events.append('deposit')
        status = deposits.pop(0)
        success = status != '入仓失败'
        return OperationResult(success, status, {'safe_count': 2} if status == BagelDeposit.STATUS_FULL else None)

    def clean_exec(self: BagelCleanWarehouse) -> OperationResult:
        events.append('clean')
        return OperationResult(True, clean_status)

    monkeypatch.setattr(BagelDeposit, 'execute', deposit_exec)
    monkeypatch.setattr(BagelCleanWarehouse, 'execute', clean_exec)
    return events


def test_clean_refuses_occupied_safe_from_real_frame(
    test_context: TestContext, controller: FixtureController,
) -> None:
    """仓满且安全箱仍有物资时，不进入批量出售。"""
    controller.set_phases([{'frame': ('贝果-仓库', '满仓安全箱余一件-20260924')}])
    op = WatchedClean(test_context)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '安全箱仍有物资' in result.status
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


def test_clean_rejects_sale_without_warehouse_space(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """出售弹窗完成但仓库占用没减少时，不能报告清理成功。"""
    controller.set_phases(_clean_phases('确认出售'))
    op = WatchedClean(test_context)
    monkeypatch.setattr(op, '_warehouse_count', lambda: 280)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '未腾位' in result.status
        assert controller.click_hit_area('贝果-仓库', '出售弹窗确认')
    finally:
        reset_running_state(test_context, op)


def test_settle_passes_custom_filter_to_clean(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """入仓后的清理接收自定义类型与品质，而不是固定默认组合。"""
    seen: list[frozenset[str]] = []
    monkeypatch.setattr(BagelDeposit, 'execute', lambda self: OperationResult(True, BagelDeposit.STATUS_DONE))

    def clean(self: BagelCleanWarehouse) -> OperationResult:
        seen.append(self.filter_areas)
        return OperationResult(True, BagelCleanWarehouse.STATUS_SKIPPED)

    monkeypatch.setattr(BagelCleanWarehouse, 'execute', clean)
    controller.set_phases([{'frame': ('贝果-仓库', '空局仓库-原生1080')}])
    op = WatchedSettle(test_context, auto_clean=True, filter_areas=('筛选-装备', '筛选-Z'))
    enter_running_state(test_context)
    try:
        assert op.execute().success
        assert seen == [frozenset(('筛选-装备', '筛选-Z'))]
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('auto_clean', [True, False])
def test_settle_full_stops_before_sale(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch, auto_clean: bool,
) -> None:
    """仓满且安全箱仍有物资时，不清理、不再次入仓。"""
    events = _patch_settle_ops(monkeypatch, [BagelDeposit.STATUS_FULL])
    controller.set_phases([{'frame': ('贝果-仓库', '空局仓库-原生1080')}])
    op = WatchedSettle(test_context, auto_clean=auto_clean)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert ('禁止批量出售' if auto_clean else '仓库已满') in result.status
        assert events == ['deposit']
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('auto_clean', [True, False])
@pytest.mark.parametrize('deposit_status', [BagelDeposit.STATUS_DONE, BagelDeposit.STATUS_EMPTY])
def test_settle_rechecks_full_capacity_after_successful_deposit(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch, auto_clean: bool, deposit_status: str,
) -> None:
    """有物入仓或空箱结算后仓库仍满时，都必须停止，空箱不能触发出售。"""
    events = _patch_settle_ops(monkeypatch, [deposit_status], BagelCleanWarehouse.STATUS_SKIPPED)
    controller.set_phases([{'frame': ('贝果-仓库', '空局仓库-原生1080')}])
    monkeypatch.setattr('zzz_od.application.bagel.bagel_screen.parse_capacity_pair', lambda _text: (280, 280))
    op = WatchedSettle(test_context, auto_clean=auto_clean)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert '仓库已满' in result.status
        should_clean = auto_clean and deposit_status == BagelDeposit.STATUS_DONE
        assert events == (['deposit', 'clean'] if should_clean else ['deposit'])
        assert not controller.click_hit_area('贝果-仓库', '返回研究站')
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('auto_clean', [True, False])
@pytest.mark.parametrize('deposit_status', [BagelDeposit.STATUS_DONE, BagelDeposit.STATUS_EMPTY])
def test_settle_preserves_verified_deposit_terminal(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch, auto_clean: bool, deposit_status: str,
) -> None:
    """空箱只跳过出售，有物按开关清理；两者都核对容量并保留原入仓状态。"""
    events = _patch_settle_ops(monkeypatch, [deposit_status])

    def read_capacity(text: str) -> tuple[int, int]:
        """只有真实末尾核验读取容量时才记录，不能提前结束结算。"""
        events.append('capacity')
        return 279, 280

    monkeypatch.setattr('zzz_od.application.bagel.bagel_screen.parse_capacity_pair', read_capacity)
    controller.set_phases([{'frame': ('贝果-仓库', '空局仓库-原生1080')}])
    op = WatchedSettle(test_context, auto_clean=auto_clean)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == deposit_status
        should_clean = auto_clean and deposit_status == BagelDeposit.STATUS_DONE
        assert events == (['deposit', 'clean', 'capacity'] if should_clean else ['deposit', 'capacity'])
        assert not controller.click_hit_area('贝果-仓库', '返回研究站')
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('case, expected', [
    ('safe_occupied', '结算后安全箱仍有物资'),
    ('count_missing', '结算后无法核对仓库容量'),
])
def test_empty_settlement_rejects_unverified_final_state(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch, case: str, expected: str, no_round_wait: None,
) -> None:
    """首次报告空箱后，末帧有残留或容量不明仍应停止，不能出售或返回。"""
    events = _patch_settle_ops(monkeypatch, [BagelDeposit.STATUS_EMPTY])
    state = '带物资仓库-r07-117s' if case == 'safe_occupied' else '空局仓库-原生1080'
    controller.set_phases([{'frame': ('贝果-仓库', state)}])
    if case == 'count_missing':
        monkeypatch.setattr('zzz_od.application.bagel.bagel_screen.parse_capacity_pair', lambda _text: None)
    op = WatchedSettle(test_context, auto_clean=True)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert not result.success
        assert expected in result.status
        assert events == ['deposit']
        assert controller.recorded_clicks == []
    finally:
        reset_running_state(test_context, op)


@pytest.mark.parametrize('auto_clean', [True, False])
@pytest.mark.parametrize('full', [True, False])
def test_empty_settlement_from_real_deposit(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch, auto_clean: bool, full: bool,
) -> None:
    """真实空箱截图经过入仓和结算节点，不点击出售；最终满仓仍停止。"""
    controller.set_phases([{'frame': ('贝果-仓库', '空局仓库-原生1080')}])
    capacity_reads: list[str] = []

    def final_capacity(text: str) -> tuple[int, int]:
        """只替换末尾容量读数，入仓仍从存档画面核验空箱。"""
        capacity_reads.append(text)
        return (280 if full else 279), 280

    monkeypatch.setattr('zzz_od.application.bagel.bagel_screen.parse_capacity_pair', final_capacity)
    op = WatchedSettle(test_context, auto_clean=auto_clean)
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success is not full
        assert len(capacity_reads) == 1
        assert controller.recorded_clicks == []
        if full:
            assert '结算后仓库已满' in result.status
        else:
            assert result.status == BagelDeposit.STATUS_EMPTY
    finally:
        reset_running_state(test_context, op)


def test_filter_confirm_retries_until_dialog_closes(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一次确认没关掉快速选择时再点，弹窗还在不去找确认出售。"""
    phases = _clean_phases('确认出售')
    index = next(
        i for i, phase in enumerate(phases)
        if phase.get('exit') == ('on_click_in', '贝果-仓库', '筛选确认')
    )
    phases.insert(index, dict(phases[index]))
    controller.set_phases(phases)
    op = WatchedClean(test_context)
    counts = iter([280, 279])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelCleanWarehouse.STATUS_DONE
        confirm = test_context.screen_loader.get_area('贝果-仓库', '筛选确认').pc_rect
        confirm_clicks = [
            point for point in controller.recorded_clicks
            if confirm.x1 <= point.x <= confirm.x2 and confirm.y1 <= point.y <= confirm.y2
        ]
        assert len(confirm_clicks) >= 2
    finally:
        reset_running_state(test_context, op)


def test_sell_click_not_applied_retries_before_preview(
    test_context: TestContext, controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一次确认出售未切画面时，重试点击并等待预览，不能空等超时。"""
    phases = _clean_phases('确认出售')
    index = next(i for i, phase in enumerate(phases) if phase.get('exit') == ('on_click_in', '贝果-仓库', '确认出售'))
    phases.insert(index, dict(phases[index]))
    controller.set_phases(phases)
    op = WatchedClean(test_context)
    counts = iter([280, 279])
    monkeypatch.setattr(op, '_warehouse_count', lambda: next(counts))
    enter_running_state(test_context)
    try:
        result = op.execute()
        assert result.success, result.status
        assert result.status == BagelCleanWarehouse.STATUS_DONE
        assert controller.phase_idx == len(phases) - 1
    finally:
        reset_running_state(test_context, op)
