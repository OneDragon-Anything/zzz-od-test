from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_safe_slots import (
    capacity_safe_screen,
    capture_scaled_safe_screen,
    native_four_slot_screen,
)

from one_dragon.utils import cv2_utils
from zzz_od.application.bagel import bagel_slots
from zzz_od.application.bagel.bagel_slots import (
    SAFE_SLOT_CENTERS,
    WAREHOUSE_SAFE_CENTERS,
    inspect_safe_slots,
)

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_native_four_slots_and_template_source() -> None:
    """原图识别四格容量，模板像素可由归档图精确重建。"""
    screen = native_four_slot_screen()
    result = inspect_safe_slots(screen)
    assert result is not None
    assert result.occupied == (0,)
    assert result.empty == (1, 2, 3)
    assert result.locked == (4,)
    raw = cv2_utils.read_image('assets/template/bagel/safe_slot_locked/raw.png')
    assert (raw == screen[858:914, 639:687]).all()


@pytest.mark.parametrize(
    'warehouse,capacity',
    [
        (False, 2),
        (False, 3),
        (True, 4),
        (True, 5),
    ],
)
def test_capacity_excludes_locks_from_empty_and_occupied(
    capacity: int, warehouse: bool
) -> None:
    """局内及仓库位置均保留原格号，不把锁定位置算成物品或空格。"""
    centers = WAREHOUSE_SAFE_CENTERS if warehouse else SAFE_SLOT_CENTERS
    screen = capacity_safe_screen(capacity, warehouse)
    result = inspect_safe_slots(screen, centers)
    assert result is not None
    assert result.occupied == (0,)
    assert result.empty == tuple(range(1, capacity))
    assert result.locked == tuple(range(capacity, 5))


def test_missing_template_is_not_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """保留一个识别前提缺失案例，不把无法识别报告成空箱。"""
    screen = native_four_slot_screen()
    monkeypatch.setattr(bagel_slots, '_safe_lock_template', lambda: None)
    assert inspect_safe_slots(screen) is None


@pytest.mark.parametrize(
    'size',
    [
        (2560, 1440),
    ],
)
def test_scaled_capture_is_recognized(size: tuple[int, int]) -> None:
    """模拟不同窗口尺寸，经截图控制器缩放后仍能识别同一四格安全箱。"""
    raw, screen = capture_scaled_safe_screen(size)
    assert raw.shape == (size[1], size[0], 3)
    assert screen.shape == (1080, 1920, 3)
    result = inspect_safe_slots(screen)
    assert result is not None
    assert result.occupied == (0,)
    assert result.empty == (1, 2, 3)
    assert result.locked == (4,)


@pytest.mark.parametrize(
    'fill',
    [
        25,
    ],
)
def test_flat_occlusion_is_unknown(test_context: TestContext, fill: int) -> None:
    """纯黑、纯灰和纯白遮挡不能被判为空格。"""
    screen = test_context.load_screen('贝果-局内', '武备箱待入箱-实机').copy()
    c = SAFE_SLOT_CENTERS[0]
    screen[c.y - 48 : c.y + 48, c.x - 48 : c.x + 48] = fill
    assert inspect_safe_slots(screen) is None


@pytest.mark.parametrize(
    'state,known',
    [
        ('帧0206', False),
        ('帧1105', True),
    ],
)
def test_live_panel_transition_keeps_ambiguity(
    test_context: TestContext, state: str, known: bool
) -> None:
    """原格子分类可能对过渡返回未知或空；可操作性由面板检查负责。"""
    screen = test_context.load_screen('贝果-局内', f'搜查面板过渡/{state}')
    slots = inspect_safe_slots(screen)
    if known:
        assert slots is not None and slots.empty == (0, 1, 2, 3, 4)
    else:
        assert slots is None
