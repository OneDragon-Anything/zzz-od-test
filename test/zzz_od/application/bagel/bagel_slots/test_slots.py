from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from zzz_od.application.bagel.bagel_slots import (
    RESULT_SLOT_CENTERS,
    SAFE_SLOT_CENTERS,
    slot_occupied,
    swap_visually_ok,
)


def _load(name: str) -> np.ndarray:
    path = next(Path('zzz-od-test/screens').rglob(name))
    return np.array(Image.open(path).convert('RGB'))


def test_live_safe_swap_failure_is_not_counted_as_success() -> None:
    """2026-09-24 满箱对换两次后源格仍在，不得把画面微变当成功。"""
    before = _load('保险箱对换失败前-20260924.webp')
    after = _load('保险箱对换失败后-20260924.webp')
    source = RESULT_SLOT_CENTERS[4]
    destination = SAFE_SLOT_CENTERS[2]
    assert slot_occupied(before, source) and slot_occupied(after, source)
    assert slot_occupied(before, destination) and slot_occupied(after, destination)
    assert not swap_visually_ok(before, after, source, destination)
