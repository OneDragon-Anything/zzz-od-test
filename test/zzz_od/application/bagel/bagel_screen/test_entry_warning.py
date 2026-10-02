import pytest

from zzz_od.application.bagel.bagel_screen import entry_warning, expected_map


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('当前装备价值为0，未达到推荐价值258000，将会面临极大挑战，是否继续前往？', '零装备价值'),
        ('存在未装备武备的代理人，是否直接出战？', '未装备武备'),
        ('未穿戴队伍装备（异体刃、抗蚀器），是否直接出战？', '未穿戴队伍装备'),
        ('未知弹窗，是否确认？', None),
        ('', None),
    ],
)
def test_entry_warning(text: str, expected: str | None) -> None:
    assert entry_warning(text) == expected


@pytest.mark.parametrize('title, accepted', [
    ('[高危]雅努斯幻境', True),
    ('高危雅努斯幻境', True),
    ('[困难]雅努斯幻境', False),
    ('困难雅努斯幻境', False),
    ('高危雅努斯', False),
])
def test_expected_map_requires_high_risk(title: str, accepted: bool) -> None:
    """结算地图必须属于高危雅努斯，困难截图只能作负样本。"""
    assert expected_map(title) is accepted
