"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_editor import add_step

from zzz_od.application.bagel.bagel_flow import (
    BagelFlow,
    draft_path,
    load_published_flow,
    read_flow,
)
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_add_plain_move_has_no_container_and_keeps_explicit_parameters(
    editor: BagelRouteEditor,
) -> None:
    """靠近箱子后新增普通移动仍无容器，参数编辑支持撤销。"""
    editor.step_list.setCurrentRow(9)
    add_step(editor, 'move')
    step = editor.step
    assert step.action == 'move' and step.target is None
    assert not editor.target_combo.isVisible() and not editor.target_help.isVisible()
    assert editor.timeout_input.value() == 45
    assert editor.tolerance_input.value() == editor.passed_input.value() == 2
    assert editor.brake_default.isChecked()
    editor.target_combo.setCurrentIndex(1)
    assert editor.step == step
    editor.timeout_default.setChecked(False)
    editor.timeout_input.setValue(90)
    editor.edit_navigation()
    editor.tolerance_default.setChecked(False)
    editor.tolerance_input.setValue(3)
    editor.passed_default.setChecked(False)
    editor.passed_input.setValue(5)
    editor.edit_point()
    changed = editor.flow
    data = editor.step.to_dict()
    assert data['navigation'] == {'timeout': 90, 'final_mode': 'coordinate'}
    assert editor.step.waypoints[0].passed_radius == 5
    editor.undo()
    assert editor.step.waypoints[0].arrival_radius == 2
    editor.redo()
    assert editor.flow == changed


def test_rebuild_tenth_step_without_any_template(
    editor: BagelRouteEditor, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """删除第十步后通过真实新增窗口重建，保存重开保持相同执行含义。"""
    editor.step_list.setCurrentRow(9)
    original = editor.step
    editor.delete_step()
    editor.step_list.setCurrentRow(8)
    monkeypatch.setattr(
        'zzz_od.gui.view.bagel.bagel_route_editor.load_published_flow',
        MagicMock(side_effect=AssertionError('新建不应读取正式模板')),
    )
    add_step(editor, 'approach', 'safe', 'small_steps', original.waypoints[-1].xy)
    editor.advanced_toggle.click()
    editor.interaction_default.click()
    editor.interaction_input.setValue(original.navigation.effective_interaction_distance)
    editor.interaction_input.editingFinished.emit()
    rebuilt = editor.step
    assert rebuilt.action == original.action and rebuilt.target == original.target
    assert [p.xy for p in rebuilt.waypoints] == [p.xy for p in original.waypoints]
    assert rebuilt.navigation.effective_timeout('safe') == original.navigation.effective_timeout('safe')
    assert rebuilt.navigation.effective_interaction_distance == original.navigation.effective_interaction_distance
    assert rebuilt.navigation.effective_final_mode('safe') == 'small_steps'
    assert editor.mode_combo.currentData() == 'small_steps'
    editor.save_draft()
    reloaded = read_flow(draft_path(editor.map_id))
    assert reloaded.steps[9] == rebuilt
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_route_editor.load_published_flow', load_published_flow)
    reopened = BagelRouteEditor(99)
    reopened.step_list.setCurrentRow(9)
    assert reopened.step == rebuilt
    assert reopened.mode_combo.currentData() == 'small_steps'
    reopened.close()
    reopened.deleteLater()


def test_switch_to_small_steps_without_previous_movement(editor: BagelRouteEditor) -> None:
    """没有前置位置、目的地又与出生点相同，仍可切换碎步且不创建方向点。"""
    flow = editor.flow
    editor._change(replace(flow, steps=(flow.steps[0], flow.steps[-1])), 0)
    add_step(editor, 'approach', 'safe', xy=editor.models[editor.map_id].spawn)
    before = editor.flow
    assert editor.mode_combo.isEnabled()
    assert editor.mode_combo.count() == 2
    assert editor.mode_combo.currentData() == 'coordinate'
    editor.mode_combo.setCurrentIndex(editor.mode_combo.findData('small_steps'))
    assert len(editor.step.waypoints) == 1
    assert not hasattr(editor, 'direction_input')
    assert editor.step.waypoints[0].xy == editor.models[editor.map_id].spawn
    editor.undo()
    assert editor.flow == before


@pytest.mark.parametrize('action', ['move', 'approach'])
@pytest.mark.parametrize('mode', ['coordinate', 'small_steps'])
def test_movement_mode_and_completion_are_independent(editor: BagelRouteEditor, action: str, mode: str) -> None:
    """两种完成条件都能使用两种移动方式，保存回读始终只有一个目的地。"""
    add_step(editor, action, mode=mode, xy=(111, 83))
    assert editor.type_input.category_combo.currentText() == '移动'
    assert editor.type_input.form.labelForField(editor.action_combo).text() == '完成条件'
    assert editor.mode_combo.currentData() == mode
    assert editor.step.navigation.final_mode == mode
    assert len(editor.step.waypoints) == 1
    assert editor.step.waypoints[0].xy == (111, 83)
    assert editor.target_combo.isVisible() == (action == 'approach')
    assert BagelFlow.from_dict(editor.flow.to_dict(), validate_order=False) == editor.flow


@pytest.mark.parametrize('action', ['spawn', 'interact', 'exit'])
def test_non_movement_creation_with_and_without_target(editor: BagelRouteEditor, action: str) -> None:
    """检查、箱子操作和退出分别验证新增入口，移动由专门场景覆盖。"""
    before = editor.flow
    add_step(editor, action, target='safe')
    assert editor.step.action == action
    if action in ('spawn', 'exit'):
        assert editor.step.target is None
    else:
        assert editor.step.target == 'safe'
    editor.undo()
    assert editor.flow == before


def test_cancel_creation_preserves_flow(editor: BagelRouteEditor) -> None:
    """取消新增不改流程或撤销栈。"""
    before = editor.flow
    count = len(editor.undo_stack[editor.map_id])
    add_step(editor, 'approach', cancel=True)
    assert editor.flow == before and len(editor.undo_stack[editor.map_id]) == count
