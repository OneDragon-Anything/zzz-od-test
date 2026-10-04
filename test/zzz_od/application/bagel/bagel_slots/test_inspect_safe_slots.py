from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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


def test_warehouse_entry_crops_warehouse_positions(monkeypatch: pytest.MonkeyPatch) -> None:
    """仓库共用入口必须裁仓库位置，不能因空格宽而碰巧通过局内坐标。"""
    path = next(Path('zzz-od-test/screens').rglob('带物资仓库-r07-117s.webp'))
    crop = MagicMock(wraps=bagel_slots.slot_crop)
    monkeypatch.setattr(bagel_slots, 'slot_crop', crop)
    assert bagel_slots.safe_occupied_indices(cv2_utils.read_image(str(path))) == (0, 1, 2, 3, 4)
    positions = {call.args[1].tuple() for call in crop.call_args_list}
    assert positions == {center.tuple() for center in WAREHOUSE_SAFE_CENTERS}


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


@pytest.mark.parametrize('capacity', [2, 3, 4, 5])
@pytest.mark.parametrize('warehouse', [False, True])
def test_capacity_excludes_locks_from_empty_and_occupied(capacity: int, warehouse: bool) -> None:
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


@pytest.mark.parametrize('size', [(1280, 720), (2560, 1440)])
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


@pytest.mark.parametrize('name,occupied,warehouse', [
    ('武备箱待入箱-实机.webp', (), False),
    ('武备箱已入箱-实机.webp', (0, 1), False),
    ('带物资仓库-r07-117s.webp', (0, 1, 2, 3, 4), True),
    ('入仓后安全箱空-实机.webp', (), True),
    ('clear_loadout_prepare_warehouse_empty.webp', (), True),
])
def test_existing_five_slot_frames(name: str, occupied: tuple[int, ...], warehouse: bool) -> None:
    """局内和仓库实拍各用自身坐标，不能因裁图重叠而混用。"""
    path = next(Path('zzz-od-test/screens').rglob(name))
    centers = WAREHOUSE_SAFE_CENTERS if warehouse else SAFE_SLOT_CENTERS
    result = inspect_safe_slots(cv2_utils.read_image(str(path)), centers)
    assert result is not None
    assert result.occupied == occupied
    assert result.locked == ()
