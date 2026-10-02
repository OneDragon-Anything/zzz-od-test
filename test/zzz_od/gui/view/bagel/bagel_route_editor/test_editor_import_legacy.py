"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from zzz_od.application.bagel.bagel_flow import (
    load_published_flow,
)
from zzz_od.application.bagel.bagel_route import BagelRouteConfig, load_default_route
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_legacy_import_does_not_change_original_or_published(
    editor: BagelRouteEditor,
) -> None:
    """导入旧文件只生成内存草稿，保留已保存坐标。"""
    config = BagelRouteConfig(99)
    route = load_default_route('janus_high_a')
    points = (replace(route.waypoints[0], xy=(114, 101)), *route.waypoints[1:])
    legacy = {'version': 2, 'routes': {route.map_id: replace(route, waypoints=points).to_dict()}}
    path = Path(config.file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(legacy, allow_unicode=True), encoding='utf-8')
    before = path.read_bytes()
    editor.import_legacy()
    assert editor.flow.steps[1].waypoints[0].xy == (114, 101)
    assert Path(config.file_path).read_bytes() == before
    assert load_published_flow(editor.map_id).steps[1].waypoints[0].xy != (114, 101)
