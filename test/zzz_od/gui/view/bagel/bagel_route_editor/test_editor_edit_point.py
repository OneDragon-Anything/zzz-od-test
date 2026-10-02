"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from dataclasses import replace

from zzz_od.application.bagel.bagel_flow import (
    NavigationOptions,
    draft_path,
    read_flow,
)
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_editing_approach_preserves_hidden_legacy_parameters(editor: BagelRouteEditor) -> None:
    """拖动、坐标和范围编辑后保存回读，保留旧高级参数与碎步方式。"""
    editor.step_list.setCurrentRow(9)
    editor._replace_step(replace(editor.step, navigation=NavigationOptions(
        timeout=123, brake_distance=4, final_mode='small_steps', interaction_distance=8,
    )))
    editor.interaction_default.setChecked(False)
    editor.interaction_input.setValue(9)
    editor.edit_navigation()
    editor.timeout_default.setChecked(False)
    editor.timeout_input.setValue(120)
    editor.edit_navigation()
    editor.tolerance_default.setChecked(False)
    editor.tolerance_input.setValue(1.5)
    editor.edit_point()
    before = editor.flow
    editor.drag_point(0, (223, 115))
    assert editor.step.waypoints[0].xy == (223, 115)
    editor.x_input.setValue(225)
    editor.y_input.setValue(117)
    editor.edit_point()
    assert editor.step.waypoints[0].xy == (225, 117)
    assert editor.step.waypoints[0].tolerance == 1.5
    assert editor.step.navigation == NavigationOptions(
        timeout=120, brake_distance=4, final_mode='small_steps', interaction_distance=9,
    )
    editor.save_draft()
    assert read_flow(draft_path(editor.map_id)) == editor.flow
    editor.undo()
    editor.undo()
    assert editor.flow == before
