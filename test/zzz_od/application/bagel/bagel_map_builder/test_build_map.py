"""通过录像输入、资源加载和独立定位验收建图，不操作游戏。"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from zzz_od.application.bagel.bagel_fixed_map import load_fixed_map
from zzz_od.application.bagel.bagel_map_builder import build_map
from zzz_od.application.bagel.bagel_map_locator import locate_on_map


def scene() -> np.ndarray:
    """确定的静态纹理，坐标真值来自裁剪位置，不取算法输出。"""
    rng = np.random.default_rng(42)
    gray = rng.integers(65, 175, (300, 400), dtype=np.uint8)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def video_file(folder: Path, crops: list[np.ndarray]) -> Path:
    """生成原生尺寸无损短录像，覆盖真实解码路径。"""
    path = folder / 'input.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'FFV1'), 5, (1920, 1080))
    assert writer.isOpened()
    try:
        for crop in crops:
            frame = np.zeros((1080, 1920, 3), np.uint8)
            frame[206:407, 1533:1734] = crop
            writer.write(frame)
    finally:
        writer.release()
    return path


def test_new_video_builds_loadable_map_with_known_positions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新录像无来源清单，未参与构建的中间位置仍可定位。"""
    world = scene()
    crops = [world[20:221, 20 + x:221 + x].copy() for x in (0, 0, 0, 4, 8, 12, 16, 20, 24, 28, 32)]
    output = tmp_path / 'result'
    build_map('janus_high_a', video_file(tmp_path, crops), output)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_fixed_map.resource_root', lambda _: output)
    snapshot = load_fixed_map('janus_high_a')
    assert snapshot.spawn == (100, 100)
    for x in (0, 14, 30):
        result = locate_on_map(snapshot, world[20:221, 20 + x:221 + x])
        assert result.position is not None, result.reason
        assert np.allclose(result.position, (100 + x, 100), atol=1, rtol=0)
    assert {p.name for p in output.iterdir()} == {'map.yml', 'map.png', 'map_mask.png'}


@pytest.mark.parametrize(
    'case',
    [
        'long_gap',
    ],
)
def test_unreliable_capture_never_publishes(tmp_path: Path, case: str) -> None:
    """无特征、没有静止原点、长空段和未观测结尾都不能伪装成完整地图。"""
    world = scene()
    still = world[20:221, 20:221].copy()
    blank = np.zeros_like(still)
    crops = {
        'blank': [blank] * 15,
        'moving_start': [world[20:221, x:201 + x] for x in (20, 25, 30)],
        'long_gap': [still] * 3 + [blank] * 6 + [still],
        'lost_end': [still] * 3 + [blank] * 4,
    }[case]
    output = tmp_path / 'result'
    with pytest.raises(ValueError):
        build_map('janus_high_a', video_file(tmp_path, crops), output)
    assert not output.exists()
    assert not list(tmp_path.glob('.bagel-build-*'))


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    """即使输入尚未读取，已有输出也必须原样保留。"""
    output = tmp_path / 'existing'
    output.mkdir()
    marker = output / 'map.yml'
    marker.write_text('preserve', encoding='utf-8')
    with pytest.raises(FileExistsError):
        build_map('janus_high_a', tmp_path / 'missing.avi', output)
    assert marker.read_text(encoding='utf-8') == 'preserve'
