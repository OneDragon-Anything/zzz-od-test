"""ZzzBackendContext.close_game() 的单元测试(独立仓)。"""

from unittest.mock import MagicMock

import pytest

from zzz_od.backend.backend_context import BackendNotReadyError, ZzzBackendContext


@pytest.fixture
def mock_ctx_game_ready():
    """游戏就绪的 mock ZContext(显式设字段,不依赖 MagicMock 默认 truthy)。"""
    ctx = MagicMock(name='ZContext')
    ctx.ready_for_application = True
    ctx.controller.is_game_window_ready = True
    ctx.controller.close_game.return_value = None
    return ctx


def test_close_game_delegates_and_returns_text(mock_ctx_game_ready):
    """close_game 应委托 controller.close_game() 并返回约定文案。"""
    backend = ZzzBackendContext(mock_ctx_game_ready)
    msg = backend.close_game()
    mock_ctx_game_ready.controller.close_game.assert_called_once()
    assert msg == '已发送关闭游戏信号,可用 check_game_window 验证'


def test_close_game_window_not_ready_raises(mock_ctx_game_ready):
    """游戏窗口未就绪时,close_game 应抛 BackendNotReadyError。"""
    mock_ctx_game_ready.controller.is_game_window_ready = False
    backend = ZzzBackendContext(mock_ctx_game_ready)
    with pytest.raises(BackendNotReadyError):
        backend.close_game()
