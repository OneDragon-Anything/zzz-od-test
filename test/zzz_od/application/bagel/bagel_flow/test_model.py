"""流程模型、资源来源、导航覆盖项与原子写入。"""

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from zzz_od.application.bagel.bagel_flow import (
    BagelFlow,
    draft_path,
    load_published_flow,
    write_flow,
)


@pytest.mark.parametrize(
    'mutation',
    [
        'duplicate',
        'store_first',
        'nan',
    ],
)
def test_invalid_flow_rejected(mutation: str) -> None:
    """拒绝坏结构和会错误执行的顺序。"""
    data = load_published_flow('janus_high_a').to_dict()
    if mutation == 'version':
        data['version'] = True
    elif mutation == 'unknown':
        data['steps'][2]['action'] = 'press_key'
    elif mutation == 'duplicate':
        data['steps'][2]['id'] = data['steps'][1]['id']
    elif mutation == 'store_first':
        data['steps'][2], data['steps'][3] = data['steps'][3], data['steps'][2]
    elif mutation == 'after_exit':
        data['steps'].insert(1, data['steps'].pop())
    elif mutation == 'nan':
        data['steps'][1]['waypoints'][0]['tolerance'] = float('nan')
    elif mutation == 'mode':
        data['steps'][1]['navigation']['final_mode'] = 'teleport'
    elif mutation == 'stage':
        data['steps'][1]['waypoints'][0]['stage'] = 'safe'
    elif mutation == 'target':
        data['steps'][1]['target'] = 'unknown'
    else:
        data['steps'][3]['navigation'] = {'timeout': 10}
    with pytest.raises(ValueError):
        BagelFlow.from_dict(data)


def test_atomic_write_failure_preserves_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """替换失败后旧草稿可加载，临时文件清理。"""
    flow = load_published_flow('janus_high_b')
    path = draft_path(flow.map_id)
    write_flow(path, flow)
    before = path.read_bytes()
    monkeypatch.setattr(Path, 'replace', MagicMock(side_effect=OSError('模拟失败')))
    with pytest.raises(OSError):
        write_flow(path, replace(flow, name='新名称'))
    assert path.read_bytes() == before
    assert not list(path.parent.glob('*.tmp'))


def test_corrupt_resource_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """坏正式资源必须报错。"""
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_flow.resource_root', lambda _: tmp_path
    )
    (tmp_path / 'flow.yml').write_text(
        yaml.safe_dump({'version': 99}), encoding='utf-8'
    )
    with pytest.raises(ValueError):
        load_published_flow('janus_high_a')
