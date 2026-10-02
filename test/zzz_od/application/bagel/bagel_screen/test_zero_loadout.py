import pytest

from zzz_od.application.bagel.bagel_screen import zero_loadout


@pytest.mark.parametrize(
    ('changes', 'expected'),
    [
        ({}, True),
        ({'武备价值': '3000'}, False),
        ({'装备价值': '60000'}, False),
        ({'道具价值': '38000'}, False),
        ({'背包数量': '1/20'}, False),
        ({'安全箱数量': '1/5'}, False),
        ({'安全箱数量': '0/0'}, False),
        ({'背包数量': ''}, False),
    ],
)
def test_zero_loadout(changes: dict[str, str], expected: bool) -> None:
    values = {
        '武备价值': '0', '装备价值': '0', '道具价值': '0',
        '背包数量': '0/20', '安全箱数量': '0/5',
    }
    values.update(changes)
    assert zero_loadout(values) is expected
