"""固定底图在独立历史截图上的坐标与拒绝行为。"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from zzz_od.application.bagel.bagel_fixed_map import load_fixed_map
from zzz_od.application.bagel.bagel_map_locator import locate_on_map
from zzz_od.application.bagel.bagel_route_vision import (
    BagelSpawnMatcher,
)

CASES: list[dict[str, object]] = json.loads((Path(__file__).parent / 'data/historical_cases.json').read_text(encoding='utf-8'))
SCREENS: Path = Path(__file__).resolve().parents[5] / 'screens/贝果-局内'


@pytest.mark.parametrize('case', CASES, ids=[f'{case["label"]}-{case["image"]}' for case in CASES])
def test_historical_positions_and_rejections(case: dict[str, object]) -> None:
    """保留旧标注的逐轴容差，不用新算法输出重写真值。"""
    if case['image'] == '__blank__':
        crop = np.zeros((201, 201, 3), np.uint8)
    else:
        frame = cv2.imdecode(np.fromfile(SCREENS / case['image'], np.uint8), cv2.IMREAD_COLOR)
        crop = frame[206:407, 1533:1734]
    result = locate_on_map(load_fixed_map(case['map_id']), crop)
    if case['expected'] is None:
        assert result.position is None
    else:
        assert result.position is not None, result.reason
        assert np.allclose(result.position, case['expected'], atol=case['tolerance'], rtol=0)
        assert result.inliers >= 8 and result.median_residual_px <= .75
    assert result.map_snapshot_id and result.elapsed_ms >= 0


def test_spawn_conflict_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """两图都声称是出生位置时，不按声明顺序抢先命中。"""
    matcher = BagelSpawnMatcher()
    for vision in matcher.routes.values():
        monkeypatch.setattr(vision, 'is_at_spawn', lambda _crop: True)
    assert matcher.match(np.zeros((201, 201, 3), np.uint8)) is None
