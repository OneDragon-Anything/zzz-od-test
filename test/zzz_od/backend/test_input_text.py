"""ZzzBackendContext.input_text() 的单元测试(独立仓)。"""

from unittest.mock import MagicMock, patch

import pytest

from one_dragon.base.config.basic_game_config import TypeInputWay
from zzz_od.backend.backend_context import BackendNotReadyError, ZzzBackendContext


@pytest.fixture
def mock_ctx_game_ready():
    """游戏就绪的 mock ZContext;默认 type_input_way=剪贴板。"""
    ctx = MagicMock(name='ZContext')
    ctx.ready_for_application = True
    ctx.controller.is_game_window_ready = True
    ctx.game_config.type_input_way = TypeInputWay.CLIPBOARD.value.value  # 'clipboard'
    return ctx


@patch('zzz_od.backend.backend_context.PcClipboard')
def test_input_text_clipboard_by_override(mock_pc_clipboard, mock_ctx_game_ready):
    """use_clipboard=True 强制走剪贴板。"""
    backend = ZzzBackendContext(mock_ctx_game_ready)
    result = backend.input_text('13800001234', use_clipboard=True)
    mock_ctx_game_ready.controller.active_window.assert_called_once()
    mock_pc_clipboard.copy_and_paste.assert_called_once_with('13800001234')
    mock_ctx_game_ready.controller.input_str.assert_not_called()
    assert result['success'] is True
    assert result['method'] == 'clipboard'


@patch('zzz_od.backend.backend_context.PcClipboard')
def test_input_text_keyboard_by_override(mock_pc_clipboard, mock_ctx_game_ready):
    """use_clipboard=False 强制走逐键(controller.input_str)。"""
    backend = ZzzBackendContext(mock_ctx_game_ready)
    result = backend.input_text('abc', use_clipboard=False)
    mock_ctx_game_ready.controller.input_str.assert_called_once_with('abc')
    mock_pc_clipboard.copy_and_paste.assert_not_called()
    assert result['method'] == 'keyboard'


@patch('zzz_od.backend.backend_context.PcClipboard')
def test_input_text_none_follows_config_clipboard(mock_pc_clipboard, mock_ctx_game_ready):
    """use_clipboard=None + 配置=clipboard → 走剪贴板。"""
    backend = ZzzBackendContext(mock_ctx_game_ready)
    backend.input_text('x', use_clipboard=None)
    mock_pc_clipboard.copy_and_paste.assert_called_once_with('x')


@patch('zzz_od.backend.backend_context.PcClipboard')
def test_input_text_none_follows_config_keyboard(mock_pc_clipboard, mock_ctx_game_ready):
    """use_clipboard=None + 配置≠clipboard → 走逐键。"""
    mock_ctx_game_ready.game_config.type_input_way = 'keyboard'
    backend = ZzzBackendContext(mock_ctx_game_ready)
    backend.input_text('x', use_clipboard=None)
    mock_ctx_game_ready.controller.input_str.assert_called_once_with('x')
    mock_pc_clipboard.copy_and_paste.assert_not_called()


@patch('zzz_od.backend.backend_context.PcClipboard')
def test_input_text_masks_sensitive_text(mock_pc_clipboard, mock_ctx_game_ready):
    """返回的 masked_text 应为脱敏文本(非明文)。"""
    backend = ZzzBackendContext(mock_ctx_game_ready)
    result = backend.input_text('13800001234', use_clipboard=True)
    assert result['masked_text'] != '13800001234'
    assert isinstance(result['masked_text'], str)


def test_input_text_window_not_ready_raises(mock_ctx_game_ready):
    """游戏窗口未就绪时 input_text 抛 BackendNotReadyError。"""
    mock_ctx_game_ready.controller.is_game_window_ready = False
    backend = ZzzBackendContext(mock_ctx_game_ready)
    with pytest.raises(BackendNotReadyError):
        backend.input_text('x')
