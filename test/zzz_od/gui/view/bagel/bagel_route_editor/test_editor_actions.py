from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt

from zzz_od.application.bagel.bagel_flow import (
    draft_path,
    read_flow,
)
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
    RoutePointItem,
)


def test_existing_step_type_is_editable_and_undo_restores_all(
    editor: BagelRouteEditor,
) -> None:
    """类型转换保留标识、名称、位置和勾选，撤销恢复原高级参数。"""
    editor.step_list.setCurrentRow(8)
    editor.check_current()
    original = editor.flow
    old = editor.step
    editor.action_combo.setCurrentIndex(editor.action_combo.findData('approach'))
    assert editor.step.action == 'approach'
    assert editor.step.id == old.id and editor.step.name == old.name
    assert editor.step.waypoints[-1].xy == old.waypoints[-1].xy
    assert editor.step.navigation.effective_timeout(
        'box'
    ) == old.navigation.effective_timeout(None)
    assert old.id in editor.checked_steps[editor.map_id]
    editor.undo()
    assert editor.flow == original
    editor.type_input.category_combo.setCurrentText('箱子操作')
    assert not editor.step.waypoints
    assert not editor.coordinate_row.isVisible()
    editor.undo()
    assert editor.flow == original


def test_export_changes_only_chosen_resource(
    editor: BagelRouteEditor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """导出只写明确的正式流程文件，不自动保存草稿。"""
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


def test_running_locks_editing_and_close_waits(
    editor: BagelRouteEditor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """开始试跑后不能编辑或销毁线程，关闭请求只请求停止。"""
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QGraphicsItem

    worker = MagicMock()
    worker.isRunning.return_value = True
    factory = MagicMock(return_value=worker)
    monkeypatch.setattr(
        'zzz_od.gui.view.bagel.bagel_route_editor.FlowTrialWorker',
        factory,
    )
    editor.step_list.setCurrentRow(1)
    editor.step_list.item(1).setCheckState(Qt.CheckState.Checked)
    editor.step_list.item(4).setCheckState(Qt.CheckState.Checked)
    selected = (editor.flow.steps[1].id, editor.flow.steps[4].id)
    editor.start_trial()
    assert factory.call_args.args[2] == selected
    assert not editor.step_list.isEnabled()
    before = editor.flow
    assert not editor.name_edit.isEnabled()
    assert not editor.map_combo.isEnabled()
    editor.drag_point(0, (999, 999))
    assert editor.flow == before
    for item in editor.view.scene().items():
        if isinstance(item, RoutePointItem):
            assert not item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    event = QCloseEvent()
    editor.closeEvent(event)
    assert not event.isAccepted()
    worker.stop.assert_called_once()
    worker.isRunning.return_value = False
    worker.ctx = None
    editor._close_pending = False
    editor._trial_finished()
    assert editor.map_combo.isEnabled()
    assert editor.worker is None
    worker.deleteLater.assert_called_once()
