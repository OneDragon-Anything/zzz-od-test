from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from zzz_od.operation.compendium.compendium_choose_mission_type import (
    CompendiumChooseMissionType,
)

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_clipped_notorious_hunt_card_scrolls_within_list(
    test_context: 'TestContext',
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双子标题被列表下沿裁切时，小步滚动以保留相邻画面的重叠。"""
    mission = test_context.compendium_service.get_mission_type_data('训练', '恶名狩猎', '冥宁芙·双子')
    assert mission is not None
    op = CompendiumChooseMissionType(test_context, mission)
    op.last_screenshot = test_context.load_screen('快捷手册', '训练-恶名狩猎-底部卡片裁切')
    drag = Mock()
    click = Mock()
    monkeypatch.setattr(test_context.controller, 'drag_to', drag)
    monkeypatch.setattr(test_context.controller, 'click', click)

    result = op.choose_mission_type()

    assert result.status == '找不到 冥宁芙·双子'
    click.assert_not_called()
    drag.assert_called_once()
    start = drag.call_args.kwargs['start']
    end = drag.call_args.kwargs['end']
    assert 500 < end.y < start.y < 940
    assert start.x == end.x
    assert start.y - end.y < 210  # 小于截图里一张卡片的纵向间距


@pytest.mark.parametrize(
    ('state', 'name', 'button_y'),
    [
        ('训练-恶名狩猎-底部卡片裁切', '「霸主侵蚀体·庞培」', 810),
        ('训练-恶名狩猎-列表底部', '初生死路屠夫', 865),
    ],
)
def test_visible_notorious_hunt_card_uses_its_go_button(
    test_context: 'TestContext',
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    name: str,
    button_y: int,
) -> None:
    """完整可见的卡片直接选择同一行的前往按钮。"""
    mission = test_context.compendium_service.get_mission_type_data('训练', '恶名狩猎', name)
    assert mission is not None
    op = CompendiumChooseMissionType(test_context, mission)
    op.last_screenshot = test_context.load_screen('快捷手册', state)
    drag = Mock()
    click = Mock(return_value=True)
    monkeypatch.setattr(test_context.controller, 'drag_to', drag)
    monkeypatch.setattr(test_context.controller, 'click', click)

    result = op.choose_mission_type()

    assert result.is_success
    drag.assert_not_called()
    click.assert_called_once()
    point = click.call_args.args[0]
    assert 1430 < point.x < 1530
    assert abs(point.y - button_y) < 20
