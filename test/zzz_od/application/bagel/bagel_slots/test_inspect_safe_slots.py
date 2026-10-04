from __future__ import annotations

from pathlib import Path

import pytest
from test.harness.bagel_safe_slots import (
    copy_safe_slot,
    lock_safe_suffix,
    native_four_slot_screen,
)

from one_dragon.utils import cv2_utils
from zzz_od.application.bagel import bagel_slots
from zzz_od.application.bagel.bagel_slots import SAFE_SLOT_CENTERS, inspect_safe_slots
from zzz_od.application.bagel.bagel_store_carried import WAREHOUSE_SAFE_CENTERS


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
    source = native_four_slot_screen()
    screen = source.copy()
    for center in centers:
        copy_safe_slot(screen, source, SAFE_SLOT_CENTERS[1], center)
    copy_safe_slot(screen, source, SAFE_SLOT_CENTERS[0], centers[0])
    result = inspect_safe_slots(lock_safe_suffix(screen, capacity, centers), centers)
    assert result is not None
    assert result.occupied == (0,)
    assert result.empty == tuple(range(1, capacity))
    assert result.locked == tuple(range(capacity, 5))


@pytest.mark.parametrize('kind', ['black', 'flat', 'ambiguous', 'gap', 'one', 'resized', 'missing_template'])
def test_unknown_slot_or_invalid_layout_is_not_empty(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """遮挡、异常布局或缺失模板均保留为未知，禁止按空箱放行。"""
    screen = native_four_slot_screen()
    if kind in ('black', 'flat', 'ambiguous'):
        screen[851:947, 312:408] = {'black': 0, 'flat': 20, 'ambiguous': 70}[kind]
    elif kind == 'gap':
        copy_safe_slot(screen, screen, SAFE_SLOT_CENTERS[4], SAFE_SLOT_CENTERS[1])
    elif kind == 'one':
        screen = lock_safe_suffix(screen, 1)
    elif kind == 'resized':
        screen = screen[::2, ::2]
    else:
        monkeypatch.setattr(bagel_slots, '_safe_lock_template', lambda: None)
    assert inspect_safe_slots(screen) is None


@pytest.mark.parametrize('name,occupied', [
    ('武备箱待入箱-实机.webp', ()),
    ('武备箱已入箱-实机.webp', (0, 1)),
    ('带物资仓库-r07-117s.webp', (0, 1, 2, 3, 4)),
    ('入仓后安全箱空-实机.webp', ()),
    ('clear_loadout_prepare_warehouse_empty.webp', ()),
])
def test_existing_five_slot_frames(name: str, occupied: tuple[int, ...]) -> None:
    """已有五格实拍保持占用判断，不能误识别锁格。"""
    path = next(Path('zzz-od-test/screens').rglob(name))
    result = inspect_safe_slots(cv2_utils.read_image(str(path)))
    assert result is not None
    assert result.occupied == occupied
    assert result.locked == ()
