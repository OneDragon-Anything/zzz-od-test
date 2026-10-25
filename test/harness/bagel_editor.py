"""通过真实对话框新增贝果步骤的测试操作。"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
)

from zzz_od.application.bagel.bagel_flow import (
    ACTION_CATEGORIES,
)
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)
from zzz_od.gui.view.bagel.bagel_step_editor import BagelStepDialog


def add_step(
    editor: BagelRouteEditor, action: str, target: str = 'box',
    mode: str = 'coordinate', xy: tuple[float, float] | None = None,
    cancel: bool = False,
) -> None:
    """通过真实新增窗口选择完整配置，避免绕过用户实际操作路径。"""
    errors: list[Exception] = []

    def fill_dialog() -> None:
        """在模态窗口事件循环内填写并提交，失败时关闭以免测试挂起。"""
        dialog = QApplication.activeModalWidget()
        try:
            assert isinstance(dialog, BagelStepDialog)
            if cancel:
                dialog.cancel_button.click()
                return
            dialog.type_input.category_combo.setCurrentText(ACTION_CATEGORIES[action])
            dialog.action_combo.setCurrentIndex(dialog.action_combo.findData(action))
            dialog.target_combo.setCurrentIndex(dialog.target_combo.findData(target))
            dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData(mode))
            if xy is not None:
                dialog.x_input.setValue(xy[0])
                dialog.y_input.setValue(xy[1])
            dialog.add_button.click()
            assert dialog.step is not None, dialog.error.text()
        except Exception as error:
            errors.append(error)
            if dialog is not None:
                dialog.reject()

    QTimer.singleShot(0, fill_dialog)
    editor.add_step()
    if errors:
        raise errors[0]
