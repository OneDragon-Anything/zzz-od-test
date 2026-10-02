"""保留旧编辑器对底图与导航坐标一致性的回归。"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from zzz_od.application.bagel.bagel_map_model import BagelMapModel
from zzz_od.application.bagel.bagel_route_vision import (
    BagelRouteVision,
    BagelSpawnMatcher,
)


@pytest.mark.parametrize('map_id', ['janus_high_a', 'janus_high_b'])
def test_map_projection_matches_navigation(
    map_id: str
) -> None:
    """投影参考帧中心与运行定位一致，透明区不能冒充可通行区。"""
    root = next(
        p.parent for p in Path(__file__).resolve().parents if p.name == 'zzz-od-test'
    )
    model = BagelMapModel.load(map_id)
    vision = BagelRouteVision(map_id)
    assert model.reference_centers
    assert np.any(model.coverage == 0)
    assert np.all(model.rgba[:, :, 3][model.coverage == 0] == 0)
    for name, center in model.reference_centers:
        path = root / 'assets' / 'game_data' / 'bagel' / map_id / name
        image = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
        located = vision.locate(image)
        assert located is not None
        assert np.linalg.norm(np.asarray(located) - center) < 2
    spawn = root / 'assets' / 'game_data' / 'bagel' / map_id / 'reference_spawn.png'
    assert (
        BagelSpawnMatcher().match(
            cv2.imdecode(np.fromfile(spawn, np.uint8), cv2.IMREAD_COLOR)
        )
        == map_id
    )
