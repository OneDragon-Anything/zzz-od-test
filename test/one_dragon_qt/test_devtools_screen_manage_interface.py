from types import SimpleNamespace
from unittest.mock import MagicMock

from one_dragon.base.screen.screen_area import ScreenArea, ScreenAreaType
from one_dragon_qt.view.devtools.devtools_screen_manage_interface import (
    DevtoolsScreenManageInterface,
)


def test_area_type_change_uses_combo_current_row() -> None:
    first_area = ScreenArea(area_name='第一行', area_type='none')
    second_area = ScreenArea(area_name='第二行', area_type='text', text='标题')
    combo = MagicMock()
    combo.currentData.return_value = ScreenAreaType.TEMPLATE
    combo.property.return_value = 1

    interface = MagicMock()
    interface.chosen_screen = SimpleNamespace(area_list=[first_area, second_area])
    interface.sender.return_value = combo
    interface.area_table.indexAt.return_value.row.return_value = 0

    DevtoolsScreenManageInterface._on_area_type_changed(interface, 0)

    combo.property.assert_not_called()
    interface.area_table.indexAt.assert_called_once_with(combo.pos.return_value)
    assert first_area.area_type == ScreenAreaType.TEMPLATE
    assert second_area.area_type == ScreenAreaType.TEXT
    assert interface.area_table_row_selected == 0
    history_record = interface._add_history_record.call_args.args[0]
    assert history_record == {
        'type': 'table_edit',
        'row_index': 0,
        'change_type': 'area_type',
        'old_value': ScreenAreaType.NONE,
        'new_value': 'template',
    }
    interface._update_area_param_display.assert_called_once_with()
