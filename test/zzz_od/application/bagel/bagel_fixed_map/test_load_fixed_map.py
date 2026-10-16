"""地图资源在移动前校验，版本缓存不能污染正在执行的快照。"""

from __future__ import annotations

import shutil
from pathlib import Path

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


@pytest.mark.parametrize(
    'key,value',
    [
        ('format_version', 2),
        ('mask', {}),
    ],
)
def test_invalid_metadata_rejected(resources: Path, key: str, value: object) -> None:
    """错误身份、版本和识别参数不能进入定位。"""
    write_metadata(resources, key, value)
    with pytest.raises(ValueError):
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
    assert second is not first and second.snapshot_id != first.snapshot_id
    assert first.blur_size == 3 and second.blur_size == 5
    assert load_fixed_map('janus_high_a') is second
