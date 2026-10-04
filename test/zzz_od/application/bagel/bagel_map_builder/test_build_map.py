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


@pytest.mark.parametrize('case', ['blank', 'moving_start', 'long_gap', 'lost_end'])
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


def test_short_interruption_recovers_without_fusing_bad_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """短暂遮挡后重新获得几何证据，只融合可靠画面。"""
    world = scene()
    still = world[20:221, 20:221].copy()
    crops = [still] * 3 + [np.zeros_like(still)] + [world[20:221, 28:229]]
    output = tmp_path / 'result'
    build_map('janus_high_a', video_file(tmp_path, crops), output)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_fixed_map.resource_root', lambda _: output)
    result = locate_on_map(load_fixed_map('janus_high_a'), world[20:221, 24:225])
    assert np.allclose(result.position, (104, 100), atol=1, rtol=0)


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    """即使输入尚未读取，已有输出也必须原样保留。"""
    output = tmp_path / 'existing'
    output.mkdir()
    marker = output / 'map.yml'
    marker.write_text('preserve', encoding='utf-8')
    with pytest.raises(FileExistsError):
        build_map('janus_high_a', tmp_path / 'missing.avi', output)
    assert marker.read_text(encoding='utf-8') == 'preserve'


@pytest.mark.parametrize('rotation,scale_step', [(1.5, 0), (0, 0.01)])
def test_cumulative_geometry_change_rejected(
    tmp_path: Path, rotation: float, scale_step: float,
) -> None:
    """逐帧小变化也不能绕过出生坐标系的旋转与尺度限制。"""
    base = scene()[20:221, 20:221]
    crops = [base] * 3 + [
        cv2.warpAffine(base, cv2.getRotationMatrix2D((100, 100), rotation * i, 1 + scale_step * i), (201, 201))
        for i in range(1, 13)
    ]
    with pytest.raises(ValueError):
        build_map('janus_high_a', video_file(tmp_path, crops), tmp_path / 'result')


def test_dynamic_markers_do_not_shift_the_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """移动的彩色图标不作为静态几何，也不污染可用于定位的底图。"""
    world = scene()
    crops = []
    for index, x in enumerate((0, 0, 0, 4, 8, 12, 16)):
        crop = world[20:221, 20 + x:221 + x].copy()
        cv2.circle(crop, (60 + index * 8, 60), 8, (0, 230, 230), -1)
        crops.append(crop)
    output = tmp_path / 'result'
    build_map('janus_high_a', video_file(tmp_path, crops), output)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_fixed_map.resource_root', lambda _: output)
    result = locate_on_map(load_fixed_map('janus_high_a'), world[20:221, 30:231])
    assert result.position is not None
    assert np.allclose(result.position, (110, 100), atol=1, rtol=0)
