"""MCP app 模块级 tool 工厂的单元测试(mock backend)。"""

import asyncio
from concurrent.futures import Future
from unittest.mock import MagicMock

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.backend.mcp import app as app_mod
from zzz_od.backend.schemas import RunStatusResult


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


def test_open_and_enter_game_nonblock_returns_started() -> None:
    backend = _mock_backend()
    tool = app_mod.make_open_and_enter_game(backend)
    res = asyncio.run(tool(block=False))
    assert res['started'] is True
    backend.start_run.assert_called_once()


def test_open_and_enter_game_concurrent_reject() -> None:
    backend = _mock_backend(start_ok=False)
    tool = app_mod.make_open_and_enter_game(backend)
    res = asyncio.run(tool(block=False))
    assert res['started'] is False and 'source' in res


def test_open_and_enter_game_block_success() -> None:
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='成功'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_and_enter_game(backend)
    assert asyncio.run(tool(block=True)) == '成功打开并进入绝区零游戏'


def test_open_and_enter_game_block_failed() -> None:
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=False, status='打开游戏失败'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_and_enter_game(backend)
    assert asyncio.run(tool(block=True)) == '打开游戏失败: 打开游戏失败'


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


def test_close_game_tool_registered() -> None:
    """close_game tool 用内联 @mcp.tool() 注册(同 check_game_window),用 list_tools 验名字。"""
    mcp = app_mod.create_mcp_server(MagicMock(name='ZzzBackendContext'))
    tools = asyncio.run(mcp.list_tools())
    assert any(t.name == 'close_game' for t in tools)
