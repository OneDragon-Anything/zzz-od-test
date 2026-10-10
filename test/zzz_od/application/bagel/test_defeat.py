"""出现 DEFEAT 时停止局内动作，不限制地图名称。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel.bagel_close_search import BagelCloseSearch
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_store import BagelStoreSafe
from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('cls,method', [
    (BagelNavigate, 'check_start'), (BagelNavigate, 'move_to_target'),
    (BagelOpenBox, 'open_box'), (BagelOpenBox, 'wait_search'),
    (BagelStoreSafe, 'store_next'), (BagelStoreSafe, 'confirm_transfer'),
    (BagelUnlockSafe, 'enter_unlock'), (BagelUnlockSafe, 'wait_unlock_ui'),
    (BagelUnlockSafe, 'timing_hits'), (BagelUnlockSafe, 'wait_search'),
    (BagelCloseSearch, 'close_panel'),
])
def test_defeat_interrupts_local_actions(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    cls: type[BagelOperation], method: str,
) -> None:
    """真实失败结算必须优先于导航、补按 F 和拖拽等动作。"""
    test_context.mock_screen('贝果-结算', '高危空局失败-原生1080')
    op = cls(test_context)
    op.screenshot()
    monkeypatch.setattr(test_context.controller, 'stop_moving_forward', MagicMock(), raising=False)
    for name in ('move_w', 'interact', 'drag_to', 'click'):
        monkeypatch.setattr(test_context.controller, name, MagicMock(), raising=False)
    result = getattr(op, method)()
    assert result.is_fail and result.status == BagelOperation.STATUS_DEFEATED
    if method == 'move_to_target':
        test_context.controller.stop_moving_forward.assert_called()
    for name in ('move_w', 'interact', 'drag_to', 'click'):
        getattr(test_context.controller, name).assert_not_called()


@pytest.mark.parametrize('screen,state,defeated', [
    ('贝果-结算', '空局失败-原生1080', True),
    ('贝果-局内', '雅努斯出生-r01-39s', False),
])
def test_defeat_does_not_require_map_title(
    test_context: TestContext, screen: str, state: str, defeated: bool,
) -> None:
    """困难结算同样识别为失败，正常局内不能误判。"""
    test_context.mock_screen(screen, state)
    op = BagelOpenBox(test_context)
    op.screenshot()
    assert op.is_bagel_result() is defeated
