from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from zzz_od.application.bagel.bagel_slots import SAFE_SLOT_CENTERS, inspect_safe_slots

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('fill', [0, 25, 255])
def test_flat_occlusion_is_unknown(test_context: TestContext, fill: int) -> None:
    """纯黑、纯灰和纯白遮挡不能被判为空格。"""
    screen = test_context.load_screen('贝果-局内', '武备箱待入箱-实机').copy()
    c = SAFE_SLOT_CENTERS[0]
    screen[c.y-48:c.y+48, c.x-48:c.x+48] = fill
    assert inspect_safe_slots(screen) is None


@pytest.mark.parametrize('state,known', [('帧0206', False), ('帧1103', False), ('帧1105', True)])
def test_live_panel_transition_keeps_ambiguity(test_context: TestContext, state: str, known: bool) -> None:
    """原格子分类可能对过渡返回未知或空；可操作性由面板检查负责。"""
    screen = test_context.load_screen('贝果-局内', f'搜查面板过渡/{state}')
    slots = inspect_safe_slots(screen)
    if known:
        assert slots is not None and slots.empty == (0, 1, 2, 3, 4)
    else:
        assert slots is None
