from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_slots import (
    RESULT_SLOT_CENTERS,
    SAFE_SLOT_CENTERS,
    WAREHOUSE_SAFE_CENTERS,
    empty_indices,
    occupied_indices,
    slot_occupied,
    swap_visually_ok,
    transfer_visually_ok,
)


def _load(name: str) -> np.ndarray:
    path = next(Path('zzz-od-test/screens').rglob(name))
    return np.array(Image.open(path).convert('RGB'))


def test_slot_occupancy_on_live_transfer_frames() -> None:
    """实机入箱前后占用变化可区分，两排结果中的空格不能误判占用。"""
    before = _load('武备箱待入箱-实机.webp')
    mid = _load('武备箱入箱中-实机.webp')
    after = _load('武备箱已入箱-实机.webp')
    assert len(RESULT_SLOT_CENTERS) == 10
    assert occupied_indices(before, RESULT_SLOT_CENTERS) == [0, 1]
    assert empty_indices(before, SAFE_SLOT_CENTERS) == [0, 1, 2, 3, 4]
    assert occupied_indices(mid, RESULT_SLOT_CENTERS) == [1]
    assert occupied_indices(mid, SAFE_SLOT_CENTERS) == [0]
    assert occupied_indices(after, RESULT_SLOT_CENTERS) == []
    assert occupied_indices(after, SAFE_SLOT_CENTERS) == [0, 1]


def test_swap_visually_ok_requires_both_sides_change() -> None:
    """对换必须两边仍占用且外观都变；画面不变不能算成功。"""
    before = _load('武备箱待入箱-实机.webp')
    swapped = before.copy()
    first = RESULT_SLOT_CENTERS[0]
    second = RESULT_SLOT_CENTERS[1]
    half = 32
    y1, x1 = int(first.y) - half, int(first.x) - half
    y2, x2 = int(second.y) - half, int(second.x) - half
    patch_a = swapped[y1:y1 + 64, x1:x1 + 64].copy()
    patch_b = swapped[y2:y2 + 64, x2:x2 + 64].copy()
    swapped[y1:y1 + 64, x1:x1 + 64] = patch_b
    swapped[y2:y2 + 64, x2:x2 + 64] = patch_a
    assert swap_visually_ok(before, swapped, first, second)
    assert not swap_visually_ok(before, before, first, second)


def test_live_safe_swap_failure_is_not_counted_as_success() -> None:
    """2026-09-24 满箱对换两次后源格仍在，不得把画面微变当成功。"""
    before = _load('保险箱对换失败前-20260924.webp')
    after = _load('保险箱对换失败后-20260924.webp')
    source = RESULT_SLOT_CENTERS[4]
    destination = SAFE_SLOT_CENTERS[2]
    assert slot_occupied(before, source) and slot_occupied(after, source)
    assert slot_occupied(before, destination) and slot_occupied(after, destination)
    assert not swap_visually_ok(before, after, source, destination)


def test_transfer_visually_ok_requires_both_sides() -> None:
    """单侧变化不能算入箱成功。"""
    before = _load('武备箱待入箱-实机.webp')
    after = _load('武备箱入箱中-实机.webp')
    assert transfer_visually_ok(
        before, after, RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[0],
    )
    assert not transfer_visually_ok(
        before, before, RESULT_SLOT_CENTERS[0], SAFE_SLOT_CENTERS[0],
    )


def test_warehouse_safe_empty_after_deposit() -> None:
    """入仓后安全箱格必须判空。"""
    filled = _load('带物资仓库-r07-117s.webp')
    cleared = _load('入仓后安全箱空-实机.webp')
    assert occupied_indices(filled, WAREHOUSE_SAFE_CENTERS) == [0, 1, 2, 3, 4]
    assert occupied_indices(cleared, WAREHOUSE_SAFE_CENTERS) == []
    assert not slot_occupied(cleared, WAREHOUSE_SAFE_CENTERS[0])


def test_slot_out_of_bounds_not_occupied() -> None:
    """越界坐标不能当成有物品。"""
    screen = np.zeros((100, 100, 3), dtype=np.uint8)
    assert not slot_occupied(screen, Point(1000, 1000))
