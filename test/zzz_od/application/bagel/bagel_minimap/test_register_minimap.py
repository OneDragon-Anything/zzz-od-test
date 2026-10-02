"""小地图参考图配准的离线验证。"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from zzz_od.application.bagel.bagel_minimap import register_minimap

SCREEN_DIR: Path = Path(__file__).resolve().parents[5] / "screens" / "贝果-局内"


def _crop(round_number: int, second: int) -> np.ndarray:
    """读取跨局原生整屏归档中的固定小地图区域。"""
    name = f"雅努斯出生-r{round_number:02d}-{second}s.webp"
    screen = cv2.imdecode(np.fromfile(str(SCREEN_DIR / name), np.uint8), cv2.IMREAD_COLOR)
    assert screen is not None
    return screen[206:407, 1533:1734]


def _mask(image: np.ndarray) -> np.ndarray:
    """屏蔽已知装饰框、中央玩家标记和高饱和动态图标。"""
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.circle(mask, (100, 100), 89, 255, -1)
    cv2.circle(mask, (100, 100), 23, 0, -1)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask[(hsv[:, :, 1] > 65) | (hsv[:, :, 2] < 65)] = 0
    return mask


def test_independent_round_a() -> None:
    """第七局能在第一局的独立参考帧上得到近似同位变换。"""
    reference = _crop(1, 39)
    current = _crop(7, 30)
    anchor = (96.0, 104.0)
    match = register_minimap(current, _mask(current), reference, _mask(reference), anchor)
    assert match is not None
    assert match.inliers >= 8
    assert np.allclose(match.player_position, anchor, atol=3)
    assert not np.allclose(match.player_position, (100, 100), atol=0.1)


@pytest.mark.parametrize("round_number, second", [(2, 32), (3, 33), (4, 27), (5, 28),
                                                 (6, 30), (8, 36), (9, 34)])
def test_other_spawns_rejected(round_number: int, second: int) -> None:
    """其他七局的出生类别不能冒充录像店复活点。"""
    reference = _crop(1, 39)
    current = _crop(round_number, second)
    assert register_minimap(current, _mask(current), reference, _mask(reference), (96, 104)) is None


@pytest.mark.parametrize("scale, angle", [(1.12, 0), (1, 8)])
def test_out_of_range_transform_rejected(scale: float, angle: float) -> None:
    """纹理充足时仍拒绝超过当前固定比例和角度假设的变换。"""
    rng = np.random.default_rng(123)
    reference = rng.integers(30, 220, size=(320, 320), dtype=np.uint8)
    transform = cv2.getRotationMatrix2D((160, 160), angle, scale)
    current = cv2.warpAffine(reference, transform, (320, 320))
    valid = np.full((320, 320), 255, np.uint8)
    assert register_minimap(current, valid, reference, valid, (160, 160)) is None


def test_insufficient_geometry_rejected() -> None:
    """没有足够静态特征时不提供位置。"""
    image = np.zeros((201, 201), np.uint8)
    valid = np.full_like(image, 255)
    assert register_minimap(image, valid, image, valid, (90, 110)) is None


def test_explicit_anchor_required() -> None:
    """缺失锚点或越界坐标不能隐式使用装饰圆心。"""
    image = np.zeros((201, 201), np.uint8)
    valid = np.full_like(image, 255)
    with pytest.raises(ValueError, match="锚点"):
        register_minimap(image, valid, image, valid, (250, 100))


def test_translation_projects_anchor_into_reference() -> None:
    """验证变换方向，并用显式锚点计算参考图坐标。"""
    rng = np.random.default_rng(42)
    reference = rng.integers(30, 220, size=(320, 320), dtype=np.uint8)
    current = cv2.warpAffine(reference, np.float32([[1, 0, 12], [0, 1, -7]]), (320, 320))
    valid = np.full((320, 320), 255, np.uint8)
    match = register_minimap(current, valid, reference, valid, (160, 160))
    assert match is not None
    assert np.allclose(match.player_position, (148, 167), atol=1)
