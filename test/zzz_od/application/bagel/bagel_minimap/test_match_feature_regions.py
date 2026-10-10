"""重复道路不能被全图比例筛选隐藏。"""

import cv2
import numpy as np

from zzz_od.application.bagel.bagel_minimap import (
    MinimapFeatures,
    extract_features,
    match_feature_regions,
    match_features,
)


def test_two_equal_distant_patterns_produce_competing_positions() -> None:
    """相同纹理分布在两处，全图匹配拒绝时分区仍须发现两个候选。"""
    random = np.random.default_rng(18)
    image = random.integers(20, 220, size=(201, 201), dtype=np.uint8)
    image = cv2.GaussianBlur(image, (3, 3), 0)
    current = extract_features(image, np.full_like(image, 255))
    count = len(current.points)
    assert count >= 8
    reference = MinimapFeatures(
        np.concatenate([current.points, current.points + (300, 0)]).astype(np.float32),
        np.concatenate([current.descriptors, current.descriptors]), (201, 501),
    )
    assert match_features(current, reference, (100, 100)) is None
    matches = match_feature_regions(current, reference, (np.arange(count), np.arange(count, count * 2)), (100, 100))
    positions = sorted(match.player_position for match in matches)
    assert np.allclose(positions, [(100, 100), (400, 100)], atol=.1)
