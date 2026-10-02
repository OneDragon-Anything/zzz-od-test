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


def test_reused_distance_geometry_matches_regular_registration() -> None:
    """分区距离复用与常规双向匹配保持相同位置。"""
    random = np.random.default_rng(7)
    image = random.integers(20, 220, size=(201, 201), dtype=np.uint8)
    current = extract_features(image, np.full_like(image, 255))
    reference = MinimapFeatures(current.points + (22, -11), current.descriptors, (240, 240))
    expected = match_features(current, reference, (100, 100))
    matches = match_feature_regions(current, reference, (), (100, 100))
    assert expected is not None and len(matches) == 1
    assert np.allclose(matches[0].player_position, expected.player_position, atol=.01)
