"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from zzz_od.application.bagel.bagel_flow import (
    draft_path,
)
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_action_reorder_invalid_save_and_undo(editor: BagelRouteEditor) -> None:
    """收集移到开箱前允许继续编辑，但禁止保存。"""
    editor.step_list.setCurrentRow(3)
    editor.move_step(-1)
    editor.save_draft()
    assert '保存失败' in editor.status.text()
    assert not draft_path(editor.map_id).exists()
    editor.undo()
    editor.save_draft()
    assert draft_path(editor.map_id).exists()
