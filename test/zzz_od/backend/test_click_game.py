"""ZzzBackendContext.click_game() 的单元测试(独立仓)。"""

from unittest.mock import MagicMock

import pytest

from zzz_od.backend.backend_context import BackendNotReadyError, ZzzBackendContext


@pytest.fixture
def mock_ctx_game_ready():
    """游戏就绪的 mock ZContext。"""
    ctx = MagicMock(name='ZContext')
    ctx.ready_for_application = True
    ctx.controller.is_game_window_ready = True
    ctx.controller.click.return_value = True
    return ctx


def test_click_game_delegates_to_controller(mock_ctx_game_ready):
    """click_game 应激活窗口并委托 controller.click(Point(x,y), press_time=...)。"""
    backend = ZzzBackendContext(mock_ctx_game_ready)
    result = backend.click_game(960, 540, press_time=0.5)
    mock_ctx_game_ready.controller.active_window.assert_called_once()
    call = mock_ctx_game_ready.controller.click.call_args
    # Point 无 __eq__(比 id),故比坐标字段而非 == Point(...)
    assert (call.args[0].x, call.args[0].y) == (960, 540)
    assert call.kwargs['press_time'] == 0.5
    assert result == {'success': True, 'x': 960, 'y': 540, 'in_window': True}


def test_click_game_out_of_window_returns_false(mock_ctx_game_ready):
    """controller.click 返 False(坐标不在窗口内)时 success/in_window=False。"""
    mock_ctx_game_ready.controller.click.return_value = False
    backend = ZzzBackendContext(mock_ctx_game_ready)
    result = backend.click_game(9999, 9999)
    assert result == {'success': False, 'x': 9999, 'y': 9999, 'in_window': False}


def test_click_game_window_not_ready_raises(mock_ctx_game_ready):
    """游戏窗口未就绪时 click_game 抛 BackendNotReadyError。"""
    mock_ctx_game_ready.controller.is_game_window_ready = False
    backend = ZzzBackendContext(mock_ctx_game_ready)
    with pytest.raises(BackendNotReadyError):
        backend.click_game(100, 100)


def test_click_game_default_press_time_zero(mock_ctx_game_ready):
    """press_time 默认 0。"""
    backend = ZzzBackendContext(mock_ctx_game_ready)
    backend.click_game(10, 20)
    assert mock_ctx_game_ready.controller.click.call_args.kwargs['press_time'] == 0.0
