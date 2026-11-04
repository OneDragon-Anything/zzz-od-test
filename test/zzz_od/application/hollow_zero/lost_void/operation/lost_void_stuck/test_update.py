from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
import pytest

from zzz_od.application.hollow_zero.lost_void.operation.lost_void_stuck import (
    LostVoidMotionDetector,
)

if TYPE_CHECKING:
    from cv2.typing import MatLike


def test_static_scene_reaches_time_threshold(world_frame: MatLike) -> None:
    """静止场景按有效时间判定，重复调用不累计时间。"""
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    image = world_frame[270:810, 480:1440]
    assert detector.update(image, 10.0) is None
    for timestamp in [10.5, 11.0, 11.5]:
        assert detector.update(image, timestamp) is False
        assert not detector.is_stuck
        assert detector.update(image, timestamp) is None
    assert detector.update(image, 12.0) is False
    assert detector.is_stuck


def test_scene_translation_clears_static_time(world_frame: MatLike) -> None:
    """用存档画面平移模拟场景位移，不依赖图标检测框变化。"""
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    image = world_frame[270:810, 480:1440]
    shifted = cv2.warpAffine(image, np.float32([[1, 0, 35], [0, 1, 0]]), (960, 540))
    detector.update(image, 10.0)
    detector.update(image, 10.5)
    assert detector.update(shifted, 11.0) is True
    assert detector.static_seconds == 0


def test_character_animation_is_excluded(world_frame: MatLike) -> None:
    """中央角色动画不能掩盖场景静止。"""
    image = world_frame[270:810, 480:1440].copy()
    animation = image.copy()
    animation[240:510, 390:570] = 255 - animation[240:510, 390:570]
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    detector.update(image, 10.0)
    assert detector.update(animation, 10.5) is False


def test_wide_character_animation_still_triggers_stuck(blocked_animation_frames: list[MatLike]) -> None:
    """真实护栏卡点中，宽翼待机动画不能被算作角色前进。"""
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    for index in range(5):
        image = blocked_animation_frames[index % 2][270:810, 480:1440]
        moved = detector.update(image, 10.0 + index * 0.5)
        if index > 0:
            assert moved is False
    assert detector.is_stuck


def test_local_background_animation_is_not_navigation(world_frame: MatLike) -> None:
    """一处旗帜或特效闪动不应当作整个场景前进。"""
    image = world_frame[270:810, 480:1440].copy()
    animated = image.copy()
    animated[:180, :240] = 255 - animated[:180, :240]
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    detector.update(image, 10.0)
    assert detector.update(animated, 10.5) is False


def test_real_scene_translation_survives_wide_character_mask(blocked_animation_frames: list[MatLike]) -> None:
    """扩大角色排除范围后，实际场景平移仍然能被识别。"""
    image = blocked_animation_frames[0][270:810, 480:1440]
    shifted = cv2.warpAffine(image, np.float32([[1, 0, 25], [0, 1, 0]]), (960, 540))
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    detector.update(image, 10.0)
    assert detector.update(shifted, 10.5) is True


def test_camera_settling_uses_fresh_baseline(world_frame: MatLike) -> None:
    """转镜头前后的画面不直接比较，仍保留有效静止时间。"""
    image = world_frame[270:810, 480:1440]
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    detector.update(image, 10.0)
    detector.update(image, 10.5)
    detector.reset(settle_until=11.0, preserve_static=True)
    assert detector.update(255 - image, 10.8) is None
    assert detector.update(255 - image, 11.0) is None
    assert detector.update(255 - image, 11.5) is False
    assert detector.static_seconds == 1.0


@pytest.mark.parametrize('restart', [False, True])
def test_pause_or_missing_samples_do_not_count(world_frame: MatLike, restart: bool) -> None:
    """暂停和长时间没有采样都不能把等待时间算成卡住。"""
    image = world_frame[270:810, 480:1440]
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    detector.update(image, 10.0)
    detector.update(image, 10.5)
    if restart:
        detector.reset()
    assert detector.update(image, 30.0) is None
    assert detector.static_seconds == 0
    assert not detector.is_stuck


def test_rendering_noise_does_not_count_as_motion(world_frame: MatLike) -> None:
    """低幅亮度噪声不算作前进。"""
    image = world_frame[270:810, 480:1440]
    noisy = np.clip(image.astype(np.int16) + 3, 0, 255).astype(np.uint8)
    detector = LostVoidMotionDetector(0.5, 2.0, 0.03)
    detector.update(image, 10.0)
    assert detector.update(noisy, 10.5) is False
