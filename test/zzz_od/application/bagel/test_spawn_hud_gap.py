from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord

if TYPE_CHECKING:
    from test.conftest import TestContext


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
    monkeypatch.setattr(app, 'round_by_find_area', lambda *_: app.round_success())
    assert app.check_spawn().status == BagelApp.STATUS_A
    assert app.attempts == 1


def test_spawn_unknown_screen_stops_after_limit(test_context: TestContext, monkeypatch) -> None:
    """持续未知画面仍留现场，不算非支持出生点。"""
    app = BagelApp(test_context, BagelConfig(1, 'one_dragon'), BagelRunRecord(1))
    monkeypatch.setattr(app, 'round_by_find_area', lambda *_: app.round_fail('未知'))
    for _ in range(3):
        assert app.check_spawn().result == OperationRoundResultEnum.WAIT
    assert app.check_spawn().status == '未识别贝果局内画面'
    assert app.attempts == 0
