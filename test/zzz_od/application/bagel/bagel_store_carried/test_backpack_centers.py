from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from zzz_od.application.bagel.bagel_store_carried import (
    WAREHOUSE_SAFE_CENTERS,
    BagelStoreCarried,
    backpack_centers,
    read_carried_backpack,
)
from zzz_od.application.bagel.bagel_transfer import carried_slot_state

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('state,expected', [
    ('clear_loadout_backpack_carried', 2),
    ('clear_loadout_prepare_warehouse_empty', 0),
])
def test_warehouse_recording(test_context: TestContext, state: str, expected: int) -> None:
    """仓库只定位左侧完整格子行，不把右侧库存当作携带物。"""
    screen = test_context.load_screen('贝果-仓库', state)
    op = BagelStoreCarried(test_context)
    # 有物帧的录像鼠标遮住「仓」字，必须等待新帧，不能放宽为模糊仓库匹配。
    assert op.round_by_find_area(screen, '贝果-仓库', '放入仓库').is_success is (expected == 0)
    centers = backpack_centers(screen)
    assert len(centers) == 30
    assert sum(carried_slot_state(screen, center) is True for center in centers) == expected
    assert all(carried_slot_state(screen, center) is False for center in WAREHOUSE_SAFE_CENTERS)


def test_settlement_rewards_are_not_backpack_items(test_context: TestContext) -> None:
    """撤离奖励会推低背包标题；格子定位不得包含上方奖励物品。"""
    screen = test_context.load_screen('贝果-仓库', '满仓安全箱余一件-20260924')
    info = read_carried_backpack(test_context, screen)
    assert info is not None and info[0] == (0, 20)
    assert info[1] > 300
    centers = backpack_centers(screen, info[1])
    assert centers and all(center.y > 350 for center in centers)
