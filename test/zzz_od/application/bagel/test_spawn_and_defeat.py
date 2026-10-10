from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_storage import BagelDragController as BagelDragController
from test.harness.bagel_storage import WatchedCloseSearch as WatchedCloseSearch
from test.harness.bagel_storage import WatchedDeposit as WatchedDeposit
from test.harness.bagel_storage import _clicks_in_area as _clicks_in_area
from test.harness.bagel_storage import controller as controller

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize(
    'screen,state,defeated',
    [
        ('贝果-结算', '空局失败-原生1080', True),
        ('贝果-局内', '雅努斯出生-r01-39s', False),
    ],
)
def test_defeat_does_not_require_map_title(
    test_context: TestContext,
    screen: str,
    state: str,
    defeated: bool,
) -> None:
    """困难结算同样识别为失败，正常局内不能误判。"""
    test_context.mock_screen(screen, state)
    op = BagelOpenBox(test_context)
    op.screenshot()
    assert op.is_bagel_result() is defeated


def test_spawn_hud_ocr_gap_recovers(test_context: TestContext, monkeypatch) -> None:
    """入场后单帧普通攻击按钮漏识别不应直接结束整局。"""
    app = BagelApp(test_context, BagelConfig(1, 'one_dragon'), BagelRunRecord(1))
    match = MagicMock(return_value='janus_high_a')
    monkeypatch.setattr(app, '_spawn_matcher', lambda: MagicMock(match=match))
    monkeypatch.setattr(app, 'round_by_find_area', lambda *_: app.round_fail('漏识别'))
    assert app.check_spawn().result == OperationRoundResultEnum.WAIT
    assert app.attempts == 0
    test_context.mock_screen('贝果-局内', '雅努斯出生-r01-39s')
    app.screenshot()
    monkeypatch.setattr(
        app,
        'round_by_find_area',
        lambda _image, _screen, area: (
            app.round_success() if area == '按键-普通攻击' else app.round_fail('未命中')
        ),
    )
    assert app.check_spawn().status == BagelApp.STATUS_A
    assert app.attempts == 1


def test_spawn_unknown_screen_stops_after_limit(
    test_context: TestContext, monkeypatch
) -> None:
    """持续未知画面仍留现场，不算非支持出生点。"""
    app = BagelApp(test_context, BagelConfig(1, 'one_dragon'), BagelRunRecord(1))
    monkeypatch.setattr(app, 'round_by_find_area', lambda *_: app.round_fail('未知'))
    for _ in range(3):
        assert app.check_spawn().result == OperationRoundResultEnum.WAIT

    result = app.check_spawn()
    assert result.status == BagelOperation.STATUS_ROUND_FAILED
    assert result.data == '未识别贝果局内画面'
    assert app.attempts == 0
