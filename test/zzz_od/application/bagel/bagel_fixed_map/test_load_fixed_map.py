"""地图资源在移动前校验，版本缓存不能污染正在执行的快照。"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from zzz_od.application.bagel.bagel_fixed_map import load_fixed_map
from zzz_od.application.bagel.bagel_route import resource_root


@pytest.fixture
def resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """每个测试独立修改资源副本，禁止写发布资源。"""
    folder = tmp_path / 'map'
    shutil.copytree(resource_root('janus_high_a'), folder)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_fixed_map.resource_root', lambda _map_id: folder)
    return folder


def write_metadata(folder: Path, key: str, value: object) -> None:
    """保留图片，仅改变待验证的元数据字段。"""
    data = yaml.safe_load((folder / 'map.yml').read_text(encoding='utf-8'))
    data[key] = value
    (folder / 'map.yml').write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')


@pytest.mark.parametrize('key,value', [
    ('format_version', 2), ('format_version', True), ('coordinate_version', 2),
    ('map_id', 'janus_high_b'), ('coordinate_unit', 'world_pixel'),
    ('origin_xy', [float('nan'), 0]), ('size_wh', [1, 1]),
    ('representations', ['unknown']), ('mask', {}), ('player_arrow', {}),
])
def test_invalid_metadata_rejected(resources: Path, key: str, value: object) -> None:
    """错误身份、版本和识别参数不能进入定位。"""
    write_metadata(resources, key, value)
    with pytest.raises(ValueError):
        load_fixed_map('janus_high_a')


@pytest.mark.parametrize('filename', ['map.png', 'map_mask.png', 'map.yml'])
def test_missing_resource_rejected(resources: Path, filename: str) -> None:
    """缺图或元数据时不回退原始参考图。"""
    (resources / filename).unlink()
    with pytest.raises(OSError):
        load_fixed_map('janus_high_a')


def test_partial_update_rejected(resources: Path) -> None:
    """缓存已有旧图时，新图片配旧摘要仍必须失败。"""
    old = load_fixed_map('janus_high_a')
    with (resources / 'map.png').open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='摘要'):
        load_fixed_map('janus_high_a')
    assert old.image.shape == (405, 305, 4)


def test_invalid_mask_rejected_even_with_updated_digest(resources: Path) -> None:
    """全空遮罩不能仅凭摘要正确被接受。"""
    data = yaml.safe_load((resources / 'map.yml').read_text(encoding='utf-8'))
    cv2.imencode('.png', np.zeros((405, 305), np.uint8))[1].tofile(resources / 'map_mask.png')
    data['sha256']['map_mask.png'] = hashlib.sha256((resources / 'map_mask.png').read_bytes()).hexdigest()
    (resources / 'map.yml').write_text(yaml.safe_dump(data), encoding='utf-8')
    with pytest.raises(ValueError, match='遮罩'):
        load_fixed_map('janus_high_a')


def test_cached_snapshot_is_immutable_and_new_execution_reloads(resources: Path) -> None:
    """同资源不重复提特征，参数更新后新快照与旧执行隔离。"""
    first = load_fixed_map('janus_high_a')
    assert load_fixed_map('janus_high_a') is first
    with pytest.raises(ValueError):
        first.image[0, 0] = 255
    with pytest.raises(ValueError):
        first.banks[0].features.descriptors[0, 0] = 0
    with pytest.raises(TypeError):
        first.arrow_settings['tip_percentile'] = 30
    write_metadata(resources, 'registration_blur_size', 5)
    second = load_fixed_map('janus_high_a')
    assert second is not first and second.version != first.version
    assert first.blur_size == 3 and second.blur_size == 5
    assert load_fixed_map('janus_high_a') is second


def test_internal_hole_does_not_define_position_validity(resources: Path) -> None:
    """玩家点无需有可用颜色像素，地图外仍拒绝。"""
    snapshot = load_fixed_map('janus_high_a')
    mask = snapshot.mask.copy()
    y, x = np.argwhere(cv2.erode(mask, np.ones((3, 3), np.uint8)) > 0)[0]
    mask[y, x] = 0
    image = snapshot.image.copy()
    image[:, :, 3] = mask
    data = yaml.safe_load((resources / 'map.yml').read_text(encoding='utf-8'))
    for name, pixels in (('map.png', image), ('map_mask.png', mask)):
        payload = cv2.imencode('.png', pixels)[1].tobytes()
        (resources / name).write_bytes(payload)
        data['sha256'][name] = hashlib.sha256(payload).hexdigest()
    (resources / 'map.yml').write_text(yaml.safe_dump(data), encoding='utf-8')
    with_hole = load_fixed_map('janus_high_a')
    assert with_hole.mask[y, x] == 0
    assert with_hole.supports_position((x, y))
    assert not with_hole.supports_position((0, 0))
    assert not with_hole.supports_position((-1, y))
    assert not with_hole.supports_position((snapshot.mask.shape[1], y))
