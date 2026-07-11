from unittest.mock import MagicMock

import pytest

from zzz_od.backend.backend_context import RunSlot


@pytest.fixture
def mock_ctx():
    """mock ZContext:run_context 可控,不依赖真实游戏/模型。"""
    ctx = MagicMock(name='ZContext')
    ctx.run_context.start_running.return_value = True
    ctx.run_context.stop_running.return_value = None
    ctx.run_context.current_application = None     # 无运行时 current_application 为 None
    ctx.current_instance_idx = 0
    return ctx


@pytest.fixture
def slot(mock_ctx):
    return RunSlot(mock_ctx)
