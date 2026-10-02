"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
)

from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
    FlowMarkerItem,
    RoutePointItem,
)


def test_non_movement_has_no_markers_and_movement_remains_clickable(
    editor: BagelRouteEditor, qapp: QApplication,
) -> None:
    """隐藏非移动标点、文字与地标后，移动点仍可选择，且不改执行勾选。"""
    original = editor.flow
    editor.step_list.setCurrentRow(3)
    items = editor.view.scene().items()
    markers = [item for item in items if isinstance(item, FlowMarkerItem)]
    destinations = [step.waypoints[-1].xy for step in original.steps if step.waypoints]
    assert sorted((item.pos().x(), item.pos().y()) for item in markers) == sorted([editor.models[editor.map_id].spawn, *destinations])
    assert len([item for item in items if isinstance(item, QGraphicsEllipseItem)]) == len(destinations) + 1
    assert [item.text() for item in items if isinstance(item, QGraphicsSimpleTextItem)] == ['出生位置']
    assert not editor.position_heading.isVisible()
    assert not editor.navigation_heading.isVisible()
    assert not editor.timeout_default.isVisible()
    assert editor.brief.isVisible()
    assert not editor.rules.isVisible()
    point = editor.view.mapFromScene(QPointF(*destinations[0]))
    QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qapp.processEvents()
    assert editor.step_list.currentRow() == 1
    assert editor.position_heading.isVisible()
    assert editor.tolerance_input.isVisible()
    assert editor.mode_combo.isVisible()
    assert editor.flow == original
    assert not editor.checked_steps[editor.map_id]
    circles = [
        item for item in editor.view.scene().items()
        if type(item) is QGraphicsEllipseItem
    ]
    point = original.steps[1].waypoints[0]
    assert sorted(item.rect().width() / 2 for item in circles) == sorted([point.arrival_radius, point.passed_radius])


def test_spawn_marker_is_fixed_and_check_range_is_selected_only(
    editor: BagelRouteEditor, qapp: QApplication,
) -> None:
    """出生点常驻可点击，只有检查步骤显示范围，鼠标拖动不改地图或流程。"""
    original = editor.flow
    editor.step_list.setCurrentRow(9)
    assert len([i for i in editor.view.scene().items() if isinstance(i, RoutePointItem)]) == 1
    assert not any(isinstance(i, QGraphicsLineItem) and i.pen().style() == Qt.PenStyle.DashLine
                   for i in editor.view.scene().items())
    assert not any(i.data(0) == 'spawn_range' for i in editor.view.scene().items())
    spawn = editor.models[editor.map_id].spawn
    start = editor.view.mapFromScene(QPointF(*spawn))
    QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qapp.processEvents()
    assert editor.step.action == 'spawn'
    circle = next(i for i in editor.view.scene().items() if i.data(0) == 'spawn_range')
    assert circle.rect().width() == 10
    end = editor.view.mapFromScene(QPointF(spawn[0] + 5, spawn[1] + 5))
    QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(editor.view.viewport(), end, delay=30)
    QTest.mouseRelease(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    qapp.processEvents()
    marker = next(i for i in editor.view.scene().items() if i.data(0) == 'spawn')
    assert marker.pos() == QPointF(*spawn)
    assert editor.flow == original


def test_trace_visibility_preserves_positions_and_gaps(editor: BagelRouteEditor) -> None:
    """轨迹开关只控制显示，重新显示后仍不能跨定位缺失处连线。"""
    original = editor.flow
    positions = [(100, 100), (102, 100), None, (110, 100), (110, 102)]
    for xy in positions:
        editor._observe({'kind': 'observation', 'position': xy, 'angle': 0})

    def trace_path() -> QGraphicsPathItem:
        """按图例颜色取得实际轨迹。"""
        return next(
            item for item in editor.view.scene().items()
            if isinstance(item, QGraphicsPathItem) and item.pen().color().name() == '#007e50'
        )

    assert trace_path().pen().style() == Qt.PenStyle.DashLine
    for visible in (False, True):
        editor.trace_check.setChecked(visible)
        path = trace_path().path()
        if visible:
            assert path.elementCount() == 4
            assert [path.elementAt(i).isMoveTo() for i in range(4)] == [True, False, True, False]
        else:
            assert path.isEmpty()
        assert editor.trace == positions
        assert editor.flow == original
    editor.map_combo.setCurrentIndex(1)
    assert editor.trace == []
