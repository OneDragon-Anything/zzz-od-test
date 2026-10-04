from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_safe_slots import lock_safe_suffix

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext

    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


@pytest.mark.parametrize('unknown', [False, True])
def test_next_round_requires_known_empty_safe(
    test_context: TestContext, config: BagelConfig, record: BagelRunRecord,
    monkeypatch: pytest.MonkeyPatch, unknown: bool,
) -> None:
    """后续局可以从有锁格的空箱进入；未知格不能触发入场操作。"""
    screen = lock_safe_suffix(test_context.load_screen('贝果-仓库', '入仓后安全箱空-r07-118s'), 4)
    if unknown:
        screen[851:947, 211:307] = 0
    test_context.add_mock_screenshot(screen)
    op = BagelApp(test_context, config, record)
    op.initial_clear_pending = False
    enter = MagicMock(return_value=OperationResult(True, '模拟入场成功'))
    monkeypatch.setattr(BagelEnter, 'execute', enter)
    result = op.enter()
    if unknown:
        assert result.is_fail and '状态不明' in result.status
        enter.assert_not_called()
    else:
        assert result.is_success
        enter.assert_called_once()
