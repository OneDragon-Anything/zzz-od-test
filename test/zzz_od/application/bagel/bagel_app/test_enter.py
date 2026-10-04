from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


def test_application_consumes_first_entry_even_before_spawn(
    config: BagelConfig, record: BagelRunRecord, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """资格按启动隔离，不因入场失败、出生点未识别或暂停而重复授予。"""
    ctx = MagicMock()
    app = BagelApp(ctx, config, record)
    monkeypatch.setattr(app, 'screenshot', MagicMock())
    monkeypatch.setattr(app, 'round_by_find_area', MagicMock(return_value=app.round_fail()))
    allowed: list[bool] = []

    def enter(op: BagelEnter) -> OperationResult:
        """记录入场资格，并模拟第一次入场尚未成功就停止。"""
        allowed.append(op.allow_clear_loadout)
        return OperationResult(False, '模拟入场失败')

    monkeypatch.setattr(BagelEnter, 'execute', enter)
    assert app.enter().is_fail
    assert app.attempts == 0
    app.handle_pause()
    app.handle_resume()
    assert app.enter().is_fail
    assert allowed == [True, False]
    app.handle_init()
    assert app.enter().is_fail
    assert allowed == [True, False, True]
