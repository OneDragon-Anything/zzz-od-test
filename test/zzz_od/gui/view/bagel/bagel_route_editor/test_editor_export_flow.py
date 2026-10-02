"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel.bagel_flow import (
    draft_path,
    read_flow,
)
from zzz_od.application.bagel.bagel_route import BagelRouteConfig
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_export_changes_only_chosen_resource(
    editor: BagelRouteEditor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """导出只写明确的正式流程文件，不动账号覆盖或自动保存草稿。"""
    dialog = MagicMock()
    dialog.exec.return_value = True
    monkeypatch.setattr(
        'zzz_od.gui.view.bagel.bagel_route_editor.MessageBox',
        MagicMock(return_value=dialog),
    )
    monkeypatch.setattr(
        'zzz_od.gui.view.bagel.bagel_route_editor.resource_root',
        lambda _: tmp_path / 'published',
    )
    editor.export_flow()
    assert read_flow(tmp_path / 'published' / 'flow.yml') == editor.flow
    assert not draft_path(editor.map_id).exists()
    assert not Path(BagelRouteConfig(99).file_path).exists()
