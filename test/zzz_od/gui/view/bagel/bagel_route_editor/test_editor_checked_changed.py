"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt

from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_checks_select_execution_and_survive_reorder(
    editor: BagelRouteEditor, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """点击行不选择执行；勾选随稳定标识保留，清单顺序随列表更新。"""
    editor.step_list.setCurrentRow(1)
    assert not editor.run_button.isEnabled()
    factory = MagicMock()
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_route_editor.FlowTrialWorker', factory)
    editor.start_trial()
    factory.assert_not_called()
    assert '勾选' in editor.trial_info.text()
    before = editor.flow
    editor.step_list.item(1).setCheckState(Qt.CheckState.Checked)
    editor.step_list.item(3).setCheckState(Qt.CheckState.Checked)
    assert editor.flow == before
    assert '2 → 4' in editor.selection_info.text()
    chosen = set(editor.checked_steps[editor.map_id])
    editor.move_step(1)
    assert editor.checked_steps[editor.map_id] == chosen
    assert '3 → 4' in editor.selection_info.text()
    editor.check_current()
    assert len(editor.checked_steps[editor.map_id]) == 1
    editor.check_steps(False)
    assert not editor.run_button.isEnabled()
