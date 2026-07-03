import asyncio
import json
from concurrent.futures import Future
from dataclasses import dataclass
from unittest.mock import MagicMock

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.backend.http import routes as routes_mod
from zzz_od.backend.schemas import RunStatusResult


@dataclass
class _FakeRequest:
    query_params: dict

    async def json(self) -> dict:
        return {}


def _mock_backend(start_ok: bool = True) -> MagicMock:
    """构造 mock ZzzBackendContext:start_run 返回 (start_ok, Future)。"""
    b = MagicMock(name='ZzzBackendContext')
    b.start_run.return_value = (start_ok, Future())
    b.query_status.return_value = RunStatusResult(
        state='running',
        source='http',
        app='OpenAndEnterGame',
        started_at='2026-07-02T00:00:00',
        duration_seconds=1.0,
    )
    b.stop.return_value = {'stopped': True, 'source': 'http'}
    return b


def test_handle_game_enter_nonblock():
    resp = asyncio.run(routes_mod.handle_game_enter(_mock_backend(), _FakeRequest({'block': 'false'})))
    assert resp.status_code == 200


def test_handle_game_enter_concurrent_reject():
    resp = asyncio.run(routes_mod.handle_game_enter(_mock_backend(start_ok=False), _FakeRequest({})))
    assert resp.status_code == 200
    assert json.loads(resp.body)['started'] is False


def test_handle_game_enter_block_success():
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=True))
    backend.start_run.return_value = (True, fut)
    resp = asyncio.run(routes_mod.handle_game_enter(backend, _FakeRequest({})))  # block 默认 true
    assert json.loads(resp.body)['result'] == '成功打开并进入绝区零游戏'


def test_handle_game_status():
    resp = asyncio.run(routes_mod.handle_game_status(_mock_backend(), _FakeRequest({})))
    assert resp.status_code == 200


def test_handle_game_stop():
    resp = asyncio.run(routes_mod.handle_game_stop(_mock_backend(), _FakeRequest({})))
    assert resp.status_code == 200


def test_handle_game_close_ok():
    backend = _mock_backend()
    backend.close_game.return_value = '已发送关闭游戏信号,可用 check_game_window 验证'
    resp = asyncio.run(routes_mod.handle_game_close(backend, _FakeRequest({})))
    assert resp.status_code == 200
    assert json.loads(resp.body)['result'] == '已发送关闭游戏信号,可用 check_game_window 验证'
