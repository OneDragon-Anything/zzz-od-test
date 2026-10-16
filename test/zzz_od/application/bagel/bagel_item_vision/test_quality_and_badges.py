from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from one_dragon.base.geometry.point import Point
from zzz_od.application.bagel.bagel_item_vision import identify_quality, identify_type


@pytest.mark.parametrize(
    'screen_name,state,center,expected',
    [
        ('贝果-仓库', '仓库角标完整-20260930', Point(1121, 330), '战术棱镜'),
        ('贝果-仓库', '装备角标完整-20260930', Point(1121, 330), '装备'),
        ('贝果-局内', '电子保险箱满箱对换失败-20260930', Point(1744, 330), '贵重物品'),
        ('贝果-仓库', '仓库角标完整-20260930', Point(1643, 820), '门禁卡'),
        ('贝果-局内', '材料占箱待换贵重物品-20260921', Point(1443, 330), '金币'),
        ('贝果-局内', '武备箱待入箱-实机', Point(1342, 330), '战术道具'),
        ('贝果-局内', '材料占箱待换贵重物品-20260921', Point(561, 899), '材料'),
    ],
    ids=['prism_char', 'equip', 'valuable', 'keycard', 'currency', 'tactic', 'material'],
)
def test_identify_complete_badges_on_native_screens(
    screen_name: str,
    state: str,
    center: Point,
    expected: str,
) -> None:
    """原生实拍的完整角标应识别为真实类型，不能用裁偏模板降级成其他。"""
    path = Path('zzz-od-test/screens') / screen_name / f'{state}.webp'
    if not path.exists():
        path = path.with_suffix('.png')
    with Image.open(path) as image:
        screen = np.array(image.convert('RGB'))
    assert identify_type(screen, center) == expected


@pytest.mark.parametrize(
    'hue,quality',
    [
        (0, 'Z'),
        (23, 'S'),
        (50, 'C'),
        (119, 'B'),
        (120, 'A'),
    ],
)
def test_identify_quality_hue_bands(hue: int, quality: str) -> None:
    """蓝紫色带独立，未覆盖的色相不猜品质。"""
    hsv = np.full((8, 8, 3), (hue, 150, 180), dtype=np.uint8)
    assert identify_quality(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)) == quality


@pytest.mark.parametrize(
    'saturation,value',
    [
        (39, 255),
        (150, 39),
    ],
)
def test_identify_quality_rejects_gray_or_dark(saturation: int, value: int) -> None:
    """灰色或过暗背景仍为未知，不能直接兜底为 B、C。"""
    hsv = np.full((8, 8, 3), (73, saturation, value), dtype=np.uint8)
    assert identify_quality(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)) == '?'
