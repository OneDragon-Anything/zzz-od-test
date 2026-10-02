"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_existing_step_type_is_editable_and_undo_restores_all(editor: BagelRouteEditor) -> None:
    """类型转换保留标识、名称、位置和勾选，撤销恢复原高级参数。"""
    editor.step_list.setCurrentRow(8)
    editor.check_current()
    original = editor.flow
    old = editor.step
    editor.action_combo.setCurrentIndex(editor.action_combo.findData('approach'))
    assert editor.step.action == 'approach'
    assert editor.step.id == old.id and editor.step.name == old.name
    assert editor.step.waypoints[-1].xy == old.waypoints[-1].xy
    assert editor.step.navigation.effective_timeout('box') == old.navigation.effective_timeout(None)
    assert old.id in editor.checked_steps[editor.map_id]
    editor.undo()
    assert editor.flow == original
    editor.type_input.category_combo.setCurrentText('箱子操作')
    assert not editor.step.waypoints
    assert not editor.coordinate_row.isVisible()
    editor.undo()
    assert editor.flow == original
