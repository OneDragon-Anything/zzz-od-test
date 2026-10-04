from __future__ import annotations

import pytest

from zzz_od.application.bagel.bagel_screen import complete_loadout


@pytest.mark.parametrize('name,value', [
    ('武备价值', ''), ('装备价值', '@0'), ('道具价值', '0 500'),
    ('背包数量', '1/0'), ('背包数量', '21/20'), ('安全箱数量', '0/5/5'),
])
def test_incomplete_values_cannot_trigger_clearing(name: str, value: str) -> None:
    """任一未知或非法读数不能当作非零触发物品搬运。"""
    values = {'武备价值': '0', '装备价值': '0', '道具价值': '78000', '背包数量': '0/20', '安全箱数量': '0/5'}
    values[name] = value
    assert not complete_loadout(values)
