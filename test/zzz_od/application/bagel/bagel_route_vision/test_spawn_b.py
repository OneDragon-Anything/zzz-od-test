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


def test_b_spawn_accepted(matcher: BagelSpawnMatcher) -> None:
    crop = _crop('白鸽工地出生-20260921-seq5s.webp')
    assert matcher.match(crop) == 'janus_high_b'
    assert matcher.vision('janus_high_b').is_at_spawn(crop)
    assert not matcher.vision('janus_high_a').is_at_spawn(crop)


def test_a_spawn_not_matched_as_b(matcher: BagelSpawnMatcher) -> None:
    crop = _crop('雅努斯出生-r01-39s.webp')
    assert matcher.match(crop) == 'janus_high_a'
    assert not matcher.vision('janus_high_b').is_at_spawn(crop)


def test_other_spawn_rejected_by_both(matcher: BagelSpawnMatcher) -> None:
    crop = _crop('雅努斯出生-r02-32s.webp')
    assert matcher.match(crop) is None


def test_b_spawn_live_recheck(matcher: BagelSpawnMatcher) -> None:
    """出生后未移动的下一帧，背景变化仍应命中白鸽工地地铁站复活点。"""
    crop = _crop('白鸽工地出生复核失败-20260922.webp')
    assert matcher.match(crop) == 'janus_high_b'


@pytest.mark.parametrize('name', [
    '白鸽出生定位不稳-导航前-20260929.webp',
    '白鸽出生定位不稳-导航后-20260929.webp',
])
def test_b_spawn_tinted_background_stays_locatable(matcher: BagelSpawnMatcher, name: str) -> None:
    """MCP 实机未移动的两帧不能因透出的场景变化而丢失出生位置。"""
    crop = _crop(name)
    position = matcher.vision('janus_high_b').locate(crop)
    assert position is not None
    assert np.allclose(position, (100, 100), atol=2)
    assert matcher.match(crop) == 'janus_high_b'


def test_b_navigate_purple_tint_locate(matcher: BagelSpawnMatcher) -> None:
    """小地图透出背后紫色场景时导航途中仍应定位，位置沿前往武备箱方向。"""
    crop = _crop('白鸽导航色调偏紫定位失败-20260929.webp')
    position = matcher.vision('janus_high_b').locate(crop)
    assert position is not None
    assert np.allclose(position, (109.3, 92.4), atol=3)
