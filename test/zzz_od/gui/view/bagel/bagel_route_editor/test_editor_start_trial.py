"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt

from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
    RoutePointItem,
)


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
