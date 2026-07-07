"""MCP 适配器的单元测试。

测试使用 MagicMock 伪造 backend，避免依赖真实游戏窗口与 ZContext。

包含两类用例（互补）：
- ``_mcp_with_backend`` + 直接 await/调用 ``Tool.fn``：覆盖 check/capture/analyze
  + close_game 工具的注册与行为（来自 understand-game 主仓归一）。
- ``_mock_backend`` + ``app_mod.make_*`` 工厂：覆盖 open_game/get_run_status
  /stop_run 的委托与 block/nonblock/失败分支（来自 backend/run-status-schema）。
"""

import asyncio
from concurrent.futures import Future
from unittest.mock import MagicMock

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.backend.backend_context import BackendNotReadyError
from zzz_od.backend.mcp import app as app_mod
from zzz_od.backend.mcp.app import create_mcp_server
from zzz_od.backend.schemas import AnalyzeScreenResult, RunStatusResult, WindowStatus


def _mcp_with_backend() -> tuple[object, MagicMock]:
    """构造一个 MCP 服务器与对应的伪造 backend。

    Returns:
        ``(mcp, backend)`` 元组：mcp 为注册了全部 game 工具的 FastMCP 实例
        （check/capture/analyze + close_game/click_game/input_text
        + open_game/get_run_status/stop_run），
        backend 为 MagicMock，可在测试中配置其方法返回值或副作用。
    """
    backend = MagicMock()
    mcp = create_mcp_server(backend)
    return mcp, backend


def _mock_backend(start_ok: bool = True) -> MagicMock:
    """构造一个 mock ZzzBackendContext,start_run 返回 (start_ok, Future)。"""
    b = MagicMock(name='ZzzBackendContext')
    b.start_run.return_value = (start_ok, Future())
    b.query_status.return_value = RunStatusResult(
        state='running',
        source='mcp',
        app='OpenAndEnterGame',
        started_at='2026-07-02T00:00:00',
        duration_seconds=1.0,
    )
    b.stop.return_value = {'stopped': False, 'error': '当前无运行'}
    return b


# ===== check/capture/analyze/close_game 工具注册与行为 =====

def test_registers_all_tools() -> None:
    """create_mcp_server 应注册全部 game 工具(open_game 替换 open_and_enter_game + 新增 click/input)。"""
    mcp, _ = _mcp_with_backend()
    names = set(mcp._tool_manager._tools.keys())
    assert {
        "check_game_window",
        "capture_game_screen",
        "analyze_screen",
        "open_game",
        "click_game",
        "input_text",
        "get_run_status",
        "stop_run",
    } <= names


def test_check_game_window_tool_error_on_not_ready() -> None:
    """check_game_window 在 backend 未就绪时返回包含「错误」的字符串。"""
    mcp, backend = _mcp_with_backend()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["check_game_window"]
    # FastMCP 工具实际可调用对象在 .fn / .func；按版本取能 call 的那个
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    assert fn is not None
    out = fn()
    assert "错误" in out


def test_analyze_tool_returns_result() -> None:
    """analyze_screen 应直接返回 backend.analyze() 的结果。"""
    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(success=True, ocr_texts=[], error=None)
    tool = mcp._tool_manager._tools["analyze_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    result = fn()
    assert result.success is True


def test_analyze_screen_tool_returns_screens_field() -> None:
    """analyze_screen tool 直接调用应返回带 screens 的 AnalyzeScreenResult(验证嵌套结构)。

    MCP 经 FastMCP/pydantic 的 JSON 序列化由框架保证(与 HTTP 同源 dataclass);
    端到端 JSON 序列化(area_type → 'text')由 HTTP 测试覆盖。此处验证 tool.fn
    返回的 dataclass 结构正确。
    """
    from one_dragon.base.screen.screen_match import (
        AreaMatchDetail,
        AreaType,
        ScreenMatch,
    )

    mcp, backend = _mcp_with_backend()
    detail = AreaMatchDetail(
        area_name='标题', area_type=AreaType.TEXT,
        x=1, y=1, width=1, height=1, text='菜单',
    )
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    backend.analyze.return_value = AnalyzeScreenResult(
        success=True, ocr_texts=[], error=None, screens=[match])
    tool = mcp._tool_manager._tools['analyze_screen']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn()
    assert result.success is True
    assert result.screens[0].screen_name == '菜单'
    assert result.screens[0].areas[0].area_type == AreaType.TEXT


def test_check_game_window_formats_status() -> None:
    """check_game_window 在就绪时应格式化输出窗口状态字段。"""
    mcp, backend = _mcp_with_backend()
    backend.check_window.return_value = WindowStatus(
        win_title="ZenlessZoneZero",
        is_win_valid=True,
        is_win_active=False,
        is_win_scale=True,
        x=10,
        y=20,
        width=1920,
        height=1080,
    )
    tool = mcp._tool_manager._tools["check_game_window"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    out = fn()
    assert "ZenlessZoneZero" in out
    assert "x=10" in out


def test_close_game_tool_registered() -> None:
    """create_mcp_server 应注册内联 close_game tool(同 check_game_window,非工厂)。"""
    mcp, _ = _mcp_with_backend()
    tools = asyncio.run(mcp.list_tools())
    assert any(t.name == "close_game" for t in tools)


def test_close_game_tool_error_on_not_ready() -> None:
    """close_game 在 backend 未就绪时返回包含「错误」的字符串(工具层兜底)。"""
    mcp, backend = _mcp_with_backend()
    backend.close_game.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["close_game"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    assert fn is not None
    out = fn()
    assert "错误" in out


def test_capture_game_screen_returns_path() -> None:
    """capture_game_screen 应保存截图并返回保存路径字符串。"""
    import numpy as np

    mcp, backend = _mcp_with_backend()
    backend.capture.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    tool = mcp._tool_manager._tools["capture_game_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    path = fn()
    assert isinstance(path, str)
    assert path.endswith(".png")


# ===== open_game 工厂委托(enter 选 op)+ get_run_status/stop_run =====

def test_open_game_nonblock_returns_started() -> None:
    backend = _mock_backend()
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=True, block=False))
    assert res['started'] is True
    backend.start_run.assert_called_once()


def test_open_game_concurrent_reject() -> None:
    backend = _mock_backend(start_ok=False)
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=True, block=False))
    assert res['started'] is False and 'source' in res


def test_open_game_block_success_enter_true() -> None:
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='成功'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_game(backend)
    assert asyncio.run(tool(enter=True, block=True)) == '成功打开并进入绝区零游戏'


def test_open_game_block_success_enter_false() -> None:
    """enter=False 成功 → 返回「打开游戏(未登录)」文案。"""
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='成功'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_game(backend)
    assert asyncio.run(tool(enter=False, block=True)) == '成功打开游戏(未登录)'


def test_open_game_block_failed() -> None:
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=False, status='打开游戏失败'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_game(backend)
    assert asyncio.run(tool(enter=True, block=True)) == '打开游戏失败: 打开游戏失败'


def test_open_game_enter_false_selects_open_game_op() -> None:
    """enter=False 时传给 start_run 的 op_factory 构造出的是 OpenGame(非 OpenAndEnterGame)。冒烟验证 Task 1 重构。"""
    from unittest.mock import MagicMock
    from zzz_od.operation.enter_game.open_game import OpenGame

    backend = _mock_backend()
    tool = app_mod.make_open_game(backend)
    asyncio.run(tool(enter=False, block=False))
    op_factory = backend.start_run.call_args[0][1]
    op = op_factory(MagicMock(name='ZContext'))
    assert isinstance(op, OpenGame)


def test_open_game_enter_true_selects_open_and_enter_game_op() -> None:
    """enter=True 时 op_factory 构造出的是 OpenAndEnterGame。"""
    from unittest.mock import MagicMock
    from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame

    backend = _mock_backend()
    tool = app_mod.make_open_game(backend)
    asyncio.run(tool(enter=True, block=False))
    op_factory = backend.start_run.call_args[0][1]
    op = op_factory(MagicMock(name='ZContext'))
    assert isinstance(op, OpenAndEnterGame)


def test_get_run_status_delegates() -> None:
    backend = _mock_backend()
    res = app_mod.make_get_run_status(backend)()
    assert isinstance(res, RunStatusResult)
    backend.query_status.assert_called_once()


def test_stop_run_delegates() -> None:
    backend = _mock_backend()
    res = app_mod.make_stop_run(backend)()
    assert res['stopped'] is False
    backend.stop.assert_called_once()


# ===== click_game / input_text 工具(内联注册,同 close_game) =====

def test_click_game_tool_registered() -> None:
    mcp, _ = _mcp_with_backend()
    tools = asyncio.run(mcp.list_tools())
    assert any(t.name == "click_game" for t in tools)


def test_click_game_tool_delegates() -> None:
    """click_game tool 直调 backend.click_game() 并原样返回。"""
    mcp, backend = _mcp_with_backend()
    backend.click_game.return_value = {'success': True, 'x': 960, 'y': 540, 'in_window': True}
    tool = mcp._tool_manager._tools['click_game']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(x=960, y=540)
    backend.click_game.assert_called_once_with(960, 540, 0.0)
    assert result['success'] is True


def test_input_text_tool_registered() -> None:
    mcp, _ = _mcp_with_backend()
    tools = asyncio.run(mcp.list_tools())
    assert any(t.name == "input_text" for t in tools)


def test_input_text_tool_delegates() -> None:
    """input_text tool 直调 backend.input_text() 并原样返回。"""
    mcp, backend = _mcp_with_backend()
    backend.input_text.return_value = {'success': True, 'method': 'clipboard', 'masked_text': '***'}
    tool = mcp._tool_manager._tools['input_text']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(text='abc', use_clipboard=True)
    backend.input_text.assert_called_once_with('abc', True)
    assert result['method'] == 'clipboard'


def test_analyze_screen_tool_passes_save_image() -> None:
    """analyze_screen tool 应把 save_image 透传给 backend.analyze,并回带 screenshot_path。"""
    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(
        success=True, ocr_texts=[], error=None, screenshot_path='/tmp/x.png')
    tool = mcp._tool_manager._tools['analyze_screen']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(save_image=True)
    backend.analyze.assert_called_once_with(None, True)
    assert result.screenshot_path == '/tmp/x.png'
