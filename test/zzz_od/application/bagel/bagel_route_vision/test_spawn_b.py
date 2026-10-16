"""白鸽工地地铁站复活点出生识别。"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from zzz_od.application.bagel.bagel_route_vision import BagelSpawnMatcher

ROOT: Path = next(path.parent for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')


@pytest.fixture
def matcher() -> BagelSpawnMatcher:
    """测试隔离配置目录时仍从项目资产读取局部参考图。"""
    return BagelSpawnMatcher()


def _crop(name: str) -> np.ndarray:
    path = ROOT / 'zzz-od-test' / 'screens' / '贝果-局内' / name
    frame = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    assert frame is not None
    return frame[206:407, 1533:1734]


def test_b_navigate_purple_tint_locate(matcher: BagelSpawnMatcher) -> None:
    """小地图透出背后紫色场景时导航途中仍应定位，位置沿前往武备箱方向。"""
    crop = _crop('白鸽导航色调偏紫定位失败-20260929.webp')
    position = matcher.vision('janus_high_b').locate(crop)
    assert position is not None
    assert np.allclose(position, (109.3, 92.4), atol=3)
