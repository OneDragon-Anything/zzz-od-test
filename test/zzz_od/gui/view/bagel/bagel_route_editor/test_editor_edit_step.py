"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_target_change_keeps_effective_settings_and_position(editor: BagelRouteEditor) -> None:
    """旧步骤隐式方式和超时在更换目标时固定为原有效值，坐标不变。"""
    editor.step_list.setCurrentRow(9)
    original = editor.flow
    step = editor.step
    assert step.navigation.final_mode == 'small_steps'
    editor.target_combo.setCurrentIndex(editor.target_combo.findData('box'))
    changed = editor.step
    assert [p.xy for p in changed.waypoints] == [p.xy for p in step.waypoints]
    assert changed.navigation.effective_final_mode('box') == 'small_steps'
    assert changed.navigation.effective_timeout('box') == step.navigation.effective_timeout('safe')
    assert changed.navigation.effective_interaction_distance == step.navigation.effective_interaction_distance
    assert [p.arrival_radius for p in changed.waypoints] == [p.arrival_radius for p in step.waypoints]
    assert all(p.stage == 'box' for p in changed.waypoints)
    editor.undo()
    assert editor.flow == original
