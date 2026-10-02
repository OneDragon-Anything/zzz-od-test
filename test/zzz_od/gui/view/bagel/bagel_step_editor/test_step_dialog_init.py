"""新增步骤对话框的地图限制。"""
from PySide6.QtWidgets import QApplication

from zzz_od.gui.view.bagel.bagel_step_editor import BagelStepDialog


def test_station_map_excludes_safe(qapp: QApplication) -> None:
    """白鸽新建不提供电子保险箱或其解锁步骤。"""
    dialog = BagelStepDialog('janus_high_b', (100, 100))
    try:
        assert dialog.target_combo.findData('safe') == -1
        dialog.type_input.category_combo.setCurrentText('箱子操作')
        assert dialog.action_combo.findData('unlock') == -1
    finally:
        dialog.close()
        dialog.deleteLater()
