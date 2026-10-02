"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
)

from zzz_od.application.bagel.bagel_flow import (
    draft_path,
    load_published_flow,
    read_flow,
)
from zzz_od.application.bagel.bagel_route import BagelRouteConfig
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_mouse_drag_and_undo_save_only_draft(
    editor: BagelRouteEditor, qapp: QApplication
) -> None:
    """Qt 鼠标拖点后撤销重做，保存只影响开发草稿。"""
    published = load_published_flow('janus_high_a')
    editor.step_list.setCurrentRow(1)
    original = editor.step.waypoints[0].xy
    start = editor.view.mapFromScene(QPointF(*original))
    end = editor.view.mapFromScene(QPointF(original[0] + 4, original[1] + 2))
    QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(editor.view.viewport(), end, delay=30)
    QTest.mouseRelease(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    qapp.processEvents()
    changed = editor.flow
    assert changed != published
    editor.undo()
    assert editor.flow == published
    editor.redo()
    assert editor.flow == changed
    editor.save_draft()
    assert read_flow(draft_path(editor.map_id)) == changed
    assert load_published_flow(editor.map_id) == published
    assert not Path(BagelRouteConfig(99).file_path).exists()
