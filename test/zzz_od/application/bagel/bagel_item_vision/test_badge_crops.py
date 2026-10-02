from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_item_vision import identify_type


@pytest.mark.parametrize(
    'stem',
    ['currency', 'tactic', 'prism_bell', 'prism_char', 'equip', 'valuable', 'keycard', 'material', 'other'],
)
def test_badge_glyph_is_complete_and_centered(stem: str) -> None:
    """白色图案应完整保留且上下左右留白接近，钻石不能贴着模板上沿。"""
    path = Path('assets/game_data/bagel/item_badges') / f'{stem}.png'
    with Image.open(path) as image:
        template = np.array(image.convert('RGB'))
    height, width = template.shape[:2]
    ys, xs = np.nonzero(template.min(axis=2) > 170)
    assert len(xs) > 50
    left, top = int(xs.min()), int(ys.min())
    right, bottom = width - 1 - int(xs.max()), height - 1 - int(ys.max())
    assert min(left, top, right, bottom) > 0
    assert abs(left - right) <= 2
    assert abs(top - bottom) <= 2


@pytest.mark.parametrize(
    ('screen_name', 'state', 'center', 'expected'),
    [
        ('贝果-仓库', '仓库角标完整-20260930', Point(1121, 330), '战术棱镜'),
        ('贝果-仓库', '装备角标完整-20260930', Point(1121, 330), '装备'),
        ('贝果-局内', '电子保险箱满箱对换失败-20260930', Point(1744, 330), '贵重物品'),
        ('贝果-仓库', '仓库角标完整-20260930', Point(1643, 820), '门禁卡'),
        ('贝果-局内', '材料占箱待换贵重物品-20260921', Point(1443, 330), '金币'),
        ('贝果-局内', '武备箱待入箱-实机', Point(1342, 330), '战术道具'),
        ('贝果-局内', '武备箱待入箱-实机', Point(1443, 330), '战术棱镜'),
        ('贝果-局内', '材料占箱待换贵重物品-20260921', Point(561, 899), '材料'),
    ],
    ids=['prism_char', 'equip', 'valuable', 'keycard', 'currency', 'tactic', 'prism_bell', 'material'],
)
def test_identify_complete_badges_on_native_screens(
    screen_name: str, state: str, center: Point, expected: str,
) -> None:
    """原生实拍的完整角标应识别为真实类型，不能用裁偏模板降级成其他。"""
    path = Path('zzz-od-test/screens') / screen_name / f'{state}.webp'
    if not path.exists():
        path = path.with_suffix('.png')
    with Image.open(path) as image:
        screen = np.array(image.convert('RGB'))
    assert identify_type(screen, center) == expected
