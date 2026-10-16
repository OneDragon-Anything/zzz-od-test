from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_SWAP,
    choose_store_action,
    inspect_occupied,
)
from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS


def _load(name: str) -> np.ndarray:
    path = next(Path('zzz-od-test/screens').rglob(name))
    return np.array(Image.open(path).convert('RGB'))


def test_identify_backpack_bc_marks_on_real_crop() -> None:
    """局部实拍覆盖绿底 C、蓝底 B 和紫底 A，空格不参与识别。"""
    screen = _load('背包BC品质局部-20260930.webp')
    assert screen.shape == (289, 518, 3)
    centers = tuple(Point(x, y) for y in (100, 228) for x in (60, 161, 262, 362, 463))
    marks = inspect_occupied(screen, centers)
    by_index = {mark.index: mark for mark in marks}
    assert {index: mark.quality for index, mark in by_index.items()} == {
        0: 'C', 1: 'B', 2: 'B', 3: 'B', 4: 'C', 5: 'A', 6: 'B',
    }
    choice = choose_store_action([by_index[1]], [by_index[0]], [])
    assert choice is not None and choice.kind == ACTION_SWAP
    assert choice.source_index == 1 and choice.dest_index == 0
    assert choose_store_action([by_index[0]], [by_index[1]], []) is None


def test_identify_electronic_safe_diamond_as_valuable() -> None:
    """电子保险箱白箱角标是材料，钻石是贵重物品，底色仍认 A/S。"""
    marks = inspect_occupied(
        _load('电子保险箱货币拾取后-20260921.webp'), RESULT_SLOT_CENTERS,
    )
    by_index = {mark.index: mark for mark in marks}
    assert by_index[1].quality == 'A'
    assert by_index[1].item_type == '材料'
    assert by_index[2].quality == 'S'
    assert by_index[2].item_type == '贵重物品'


def test_identify_red_background_with_gold_icon() -> None:
    """原始像素与有损压缩样本均须识别红底 Z，金色图案不能干扰品质。"""
    for name in ('武备箱红底金图案-20260921-无损.webp', '武备箱红底金图案-20260921.webp'):
        marks = inspect_occupied(_load(name), RESULT_SLOT_CENTERS)
        assert {mark.index: mark.quality for mark in marks} == {0: 'S', 1: 'S', 2: 'Z'}


def test_material_badges_and_safe_replacement_on_real_frame() -> None:
    """箱子角标材料单独识别，满箱时优先换出材料。"""
    screen = _load('材料占箱待换贵重物品-20260921.webp')
    safe = inspect_occupied(screen, SAFE_SLOT_CENTERS)
    assert {mark.index for mark in safe if mark.item_type == '材料'} == {3, 4}
    results = inspect_occupied(screen, RESULT_SLOT_CENTERS)
    by_index = {mark.index: mark for mark in results}
    assert by_index[1].item_type == '金币'
    choice = choose_store_action(results, safe, [])
    assert choice is not None and choice.kind == ACTION_SWAP
    assert choice.source_index != 1
    assert choice.dest_index == 4
