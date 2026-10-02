"""仅加载当前仓库中已归档的参考图与整屏截图。"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision

ROOT: Path = next(path.parent for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')


@pytest.fixture
def vision() -> BagelRouteVision:
    """测试隔离配置目录时仍从项目资产读取局部参考图。"""
    return BagelRouteVision()


def archived_crop(round_number: int, second: int, near_box: bool = False) -> np.ndarray:
    """从归档的完整录像帧裁出原生小地图。"""
    name = '雅努斯箱前-r07-32s.webp' if near_box else f'雅努斯出生-r{round_number:02d}-{second}s.webp'
    return archived_state(name)


def archived_state(name: str) -> np.ndarray:
    """读取指定的贝果局内整屏存档并截取定位小地图。"""
    path = ROOT / 'zzz-od-test' / 'screens' / '贝果-局内' / name
    frame = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    assert frame is not None
    return frame[206:407, 1533:1734]
