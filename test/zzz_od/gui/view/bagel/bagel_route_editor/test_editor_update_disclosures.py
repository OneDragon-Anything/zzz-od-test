"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from zzz_od.application.bagel.bagel_flow import (
    draft_path,
    read_flow,
)
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_disclosures_preserve_custom_values_and_draft(editor: BagelRouteEditor) -> None:
    """折叠不重置迁移参数，编辑坐标、保存和撤销仍保留高级设置。"""
    editor.step_list.setCurrentRow(8)
    original = editor.flow
    nav = editor.step.navigation
    passed = editor.step.waypoints[0].passed_tolerance
    assert nav.brake_distance == 6
    assert editor.name_edit.isVisible() and editor.point_name.isVisible()
    assert editor.x_input.isVisible() and editor.y_input.isVisible()
    assert not editor.timeout_input.isVisible()
    assert not editor.passed_input.isVisible()
    assert not editor.brake_input.isVisible()
    assert not editor.rules.isVisible()
    assert '有单独设置' in editor.advanced_toggle.text()
    editor.advanced_toggle.click()
    editor.help_toggle.click()
    assert editor.timeout_input.isVisible()
    assert editor.brake_input.value() == 6
    assert editor.rules.isVisible()
    editor.advanced_toggle.click()
    editor.help_toggle.click()
    assert editor.flow == original
    assert not editor.undo_stack[editor.map_id]
    editor.x_input.setValue(editor.x_input.value() + 1)
    editor.edit_point()
    assert editor.step.navigation == nav
    assert editor.step.waypoints[0].passed_tolerance == passed
    editor.save_draft()
    assert read_flow(draft_path(editor.map_id)) == editor.flow
    editor.undo()
    assert editor.flow == original


def test_disclosures_follow_step_type_without_resetting_editor(
    editor: BagelRouteEditor,
) -> None:
    """已展开区域随动作显示适用字段，切到非移动不泄漏旧参数和说明。"""
    editor.step_list.setCurrentRow(1)
    original = editor.flow
    editor.advanced_toggle.click()
    editor.help_toggle.click()
    assert editor.timeout_input.isVisible() and editor.passed_input.isVisible()
    editor.step_list.setCurrentRow(9)
    assert editor.timeout_input.isVisible()
    assert not editor.passed_input.isVisible() and not editor.brake_input.isVisible()
    assert editor.interaction_input.isVisible() and editor.target_help.isVisible()
    assert editor.position_heading.text() == '目的地 · 地图像素'
    assert (editor.x_input.value(), editor.y_input.value()) == editor.step.waypoints[-1].xy
    editor.step_list.setCurrentRow(10)
    assert editor.rules.isVisible()
    assert not editor.advanced_toggle.isVisible()
    assert not editor.coordinate_row.isVisible()
    assert not editor.parameter_help.isVisible() and not editor.target_help.isVisible()
    editor.step_list.setCurrentRow(1)
    assert editor.timeout_input.isVisible() and editor.passed_input.isVisible()
    assert editor.flow == original
