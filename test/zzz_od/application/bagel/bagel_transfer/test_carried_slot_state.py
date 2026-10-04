from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from zzz_od.application.bagel.bagel_clear_loadout import LOADOUT_CENTERS
from zzz_od.application.bagel.bagel_transfer import carried_slot_state

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('state,occupied', [
    ('clear_loadout_carried', 10), ('clear_loadout_empty', 0), ('clear_loadout_tools_only', 4),
])
def test_prepare_slot_recording(test_context: TestContext, state: str, occupied: int) -> None:
    """空槽灰色图案与左侧库存不得算作已装备物品。"""
    screen = test_context.load_screen('贝果-备战', state)
    states = [carried_slot_state(screen, center) for center in LOADOUT_CENTERS]
    assert None not in states, states
    assert sum(states) == occupied, states


def test_black_image_is_unknown(test_context: TestContext) -> None:
    """无图像不能当作空槽。"""
    screen = np.zeros_like(test_context.load_screen('贝果-备战', 'clear_loadout_empty'))
    assert all(carried_slot_state(screen, center) is None for center in LOADOUT_CENTERS)
