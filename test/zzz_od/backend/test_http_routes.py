"""HTTP ``/game/*`` 适配器的单元测试。

包含两类互补用例：

- **直接 await 处理器**（async 风格）：避开 MCP 协议层，backend 用 ``MagicMock`` 伪造，
  避免依赖真实游戏窗口与 ``ZContext``。``capture`` 用例给真实 numpy 图（可编码），
  以验证 PNG 字节回传链路；``route_dispatch_*`` 用例经 Starlette 路由层分发。
- **asyncio.run 处理器**（路由参数分发风格）：覆盖 ``/game/enter?block=``
  nonblock/并发拒绝/block 成功、``/game/status``、``/game/stop`` 等分支。
"""

import asyncio
import json
from concurrent.futures import Future
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.backend.backend_context import BackendNotReadyError
from zzz_od.backend.http import routes as routes_mod
from zzz_od.backend.http.routes import (
    handle_game_analyze,
    handle_game_capture,
    handle_game_close,
    handle_game_enter,
    handle_game_window,
)
from zzz_od.backend.schemas import AnalyzeScreenResult, RunStatusResult, WindowStatus


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


# ===== 直接 await 处理器（async 风格）=====

@pytest.mark.asyncio
async def test_handle_game_window_ok() -> None:
    """handle_game_window 在就绪时应以 200 返回窗口状态 JSON。"""
    backend = MagicMock()
    backend.check_window.return_value = WindowStatus(
        win_title="绝区零", is_win_valid=True, is_win_active=False, is_win_scale=True, x=1, y=2, width=3, height=4
    )
    resp = await handle_game_window(backend)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["win_title"] == "绝区零"
    assert data["x"] == 1


@pytest.mark.asyncio
async def test_handle_game_window_error() -> None:
    """handle_game_window 在 backend 未就绪时应返回 503。"""
    backend = MagicMock()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    resp = await handle_game_window(backend)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_handle_game_capture_returns_png_bytes() -> None:
    """handle_game_capture 应直接回传 PNG 字节（media_type=image/png，不落盘）。"""
    import numpy as np

    backend = MagicMock()
    backend.capture.return_value = np.zeros((1, 1, 3), dtype="uint8")  # 可编码的 1x1 RGB 图
    resp = await handle_game_capture(backend)
    assert resp.status_code == 200
    assert resp.media_type == "image/png"
    assert resp.body[:4] == b"\x89PNG"  # PNG magic


@pytest.mark.asyncio
async def test_handle_game_analyze_ok() -> None:
    """handle_game_analyze 在成功时应以 200 返回分析结果 JSON。"""
    backend = MagicMock()
    backend.analyze.return_value = AnalyzeScreenResult(success=True, ocr_texts=[], error=None)
    resp = await handle_game_analyze(backend)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["success"] is True
    assert data["vision_hint"] is None  # HTTP 显式补字段(P11 对称);mock 未设 → None


@pytest.mark.asyncio
async def test_handle_game_analyze_returns_screens() -> None:
    """HTTP /game/analyze 返回 JSON 含 screens 嵌套;area_type 经 asdict+json 序列化为 'text'。"""
    from one_dragon.base.screen.screen_match import (
        AreaMatchDetail,
        AreaType,
        ScreenMatch,
    )

    detail = AreaMatchDetail(
        area_name='标题', area_type=AreaType.TEXT,
        x=1, y=1, width=1, height=1, text='菜单', confidence=0.9,
    )
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    backend = MagicMock()
    backend.analyze.return_value = AnalyzeScreenResult(
        success=True, ocr_texts=[], error=None, screens=[match])
    resp = await handle_game_analyze(backend)  # _request 默认 None,处理器不读 request
    assert resp.status_code == 200
    body = json.loads(resp.body.decode('utf-8'))
    assert body['success'] is True
    assert body['screens'][0]['screen_name'] == '菜单'
    # str Enum 经 asdict 保 Enum 对象、json.dumps 序列化为 'text';与 AreaType.TEXT('text') 相等
    assert body['screens'][0]['areas'][0]['area_type'] == AreaType.TEXT


@pytest.mark.asyncio
async def test_handle_game_analyze_save_image_param() -> None:
    """handle_game_analyze 从 query 读 save_image 并透传,响应含 screenshot_path。"""
    backend = MagicMock()
    backend.analyze.return_value = AnalyzeScreenResult(
        success=True, ocr_texts=[], error=None, screenshot_path='/tmp/x.png')
    request = MagicMock()
    request.query_params = {'save_image': 'true'}
    resp = await handle_game_analyze(backend, request)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode('utf-8'))
    assert data['screenshot_path'] == '/tmp/x.png'
    backend.analyze.assert_called_once_with(None, True)


@pytest.mark.asyncio
async def test_handle_game_analyze_save_image_default_false() -> None:
    """无 request 时 save_image 默认 False(向后兼容旧调用)。"""
    backend = MagicMock()
    backend.analyze.return_value = AnalyzeScreenResult(success=True, ocr_texts=[], error=None)
    resp = await handle_game_analyze(backend)  # request 默认 None
    assert resp.status_code == 200
    backend.analyze.assert_called_once_with(None, False)


@pytest.mark.asyncio
async def test_handle_game_enter_ok() -> None:
    """handle_game_enter 应委托 backend.start_run，返回 started/result JSON。

    block=true（默认）且 start_run 返回 (True, 已完成 Future) 时，
    响应体应包含 result 文本（success → 「成功打开并进入绝区零游戏」）。
    """
    from dataclasses import dataclass as _dataclass

    @_dataclass
    class _OpResult:
        success: bool
        status: str = ""

    fut: Future = Future()
    fut.set_result(_OpResult(success=True))
    backend = MagicMock()
    backend.start_run.return_value = (True, fut)
    backend.query_status.return_value = RunStatusResult(
        state="running", source="http", app="OpenAndEnterGame",
        started_at="2026-07-02T00:00:00", duration_seconds=1.0,
    )
    resp = await handle_game_enter(backend, _FakeRequest({}))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["result"] == "成功打开并进入绝区零游戏"
    backend.start_run.assert_called_once()


def test_register_http_routes_adds_custom_routes() -> None:
    """register_http_routes 应在 FastMCP 上挂载 /game/* 路由。"""
    from mcp.server.fastmcp import FastMCP

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    register_http_routes(mcp, MagicMock())
    # custom_route 挂在 Starlette 层；用 streamable_http_app 的 routes 校验
    app = mcp.streamable_http_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert any(p and "game" in p for p in paths)


@pytest.mark.asyncio
async def test_handle_game_close_ok() -> None:
    """handle_game_close 在就绪时应以 200 返回 backend.close_game() 文本。"""
    backend = MagicMock()
    backend.close_game.return_value = "已发送关闭游戏信号,可用 check_game_window 验证"
    resp = await handle_game_close(backend)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["result"] == "已发送关闭游戏信号,可用 check_game_window 验证"


@pytest.mark.asyncio
async def test_handle_game_close_error() -> None:
    """handle_game_close 在 backend 未就绪时应返回 503。"""
    backend = MagicMock()
    backend.close_game.side_effect = BackendNotReadyError("未就绪")
    resp = await handle_game_close(backend)
    assert resp.status_code == 503


def test_route_dispatch_game_close_ok() -> None:
    """经路由层分发 POST /game/close,应返回 200 + result 文本。"""
    from mcp.server.fastmcp import FastMCP
    from starlette.testclient import TestClient

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    backend = MagicMock()
    backend.close_game.return_value = "已发送关闭游戏信号,可用 check_game_window 验证"
    register_http_routes(mcp, backend)
    client = TestClient(mcp.streamable_http_app())
    resp = client.post("/game/close")
    assert resp.status_code == 200
    assert resp.json()["result"] == "已发送关闭游戏信号,可用 check_game_window 验证"


def test_route_dispatch_window_ok() -> None:
    """经 Starlette 路由层分发 GET /game/window，应返回 200 + 窗口状态 JSON。

    回归 ``register_http_routes`` 中同步 lambda 返回 coroutine 的 bug：
    处理器未走真实路由分发，上面几个直调 ``handle_*`` 的用例无法覆盖。
    """
    from mcp.server.fastmcp import FastMCP
    from starlette.testclient import TestClient

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    backend = MagicMock()
    backend.check_window.return_value = WindowStatus(
        win_title="绝区零", is_win_valid=True, is_win_active=False, is_win_scale=True
    )
    register_http_routes(mcp, backend)
    client = TestClient(mcp.streamable_http_app())
    resp = client.get("/game/window")
    assert resp.status_code == 200
    assert resp.json()["win_title"] == "绝区零"


def test_route_dispatch_predefined_teams_ok() -> None:
    """GET /game/predefined-teams 返回 200 + 编队列表 JSON(含单队字段序列化)。"""
    from mcp.server.fastmcp import FastMCP
    from starlette.testclient import TestClient

    from zzz_od.backend.http.routes import register_http_routes
    from zzz_od.backend.schemas import PredefinedTeamItem, PredefinedTeamListResult

    mcp = FastMCP("test")
    backend = MagicMock()
    backend.list_predefined_teams.return_value = PredefinedTeamListResult(
        current_instance_idx=1,
        teams=[PredefinedTeamItem(
            idx=0, name='冰雅狼苍', auto_battle='全配队通用',
            agent_id_list=['a', 'b'], agent_name_list=['雅', '莱卡恩'], weakness_list=['冰属性'],
        )],
    )
    register_http_routes(mcp, backend)
    client = TestClient(mcp.streamable_http_app())
    resp = client.get("/game/predefined-teams")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_instance_idx"] == 1
    assert body["teams"] == [{
        'idx': 0, 'name': '冰雅狼苍', 'auto_battle': '全配队通用',
        'agent_id_list': ['a', 'b'], 'agent_name_list': ['雅', '莱卡恩'], 'weakness_list': ['冰属性'],
    }]


def test_route_dispatch_window_not_ready() -> None:
    """经路由层分发，backend 未就绪时应返回 503（而非 500）。"""
    from mcp.server.fastmcp import FastMCP
    from starlette.testclient import TestClient

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    backend = MagicMock()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    register_http_routes(mcp, backend)
    client = TestClient(mcp.streamable_http_app())
    resp = client.get("/game/window")
    assert resp.status_code == 503


# ===== asyncio.run 处理器（block/nonblock/status/stop 分支）=====

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


# ===== /game/operations / /game/operations/describe / /game/run/operation(自定义 op)=====

_OPEN_AND_ENTER = 'zzz_od.operation.enter_game.open_and_enter_game.OpenAndEnterGame'
_MAP_TRANSPORT = 'zzz_od.operation.map_transport.MapTransport'
_CHARGE_PLAN_ITEM = 'zzz_od.application.charge_plan.charge_plan_config.ChargePlanItem'


def _request_with_body(query: dict, body: dict | None) -> MagicMock:
    """构造带 query_params 与 async json() body 的 fake request。"""
    request = MagicMock()
    request.query_params = query

    async def _json() -> dict:
        return body if body is not None else {}

    request.json = _json
    return request


def test_handle_game_operations_list() -> None:
    """GET /game/operations 返回 operation 列表(含 OpenAndEnterGame)。"""
    from zzz_od.backend.http.service_routes import handle_game_operations

    backend = MagicMock()
    resp = asyncio.run(handle_game_operations(backend))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode('utf-8'))
    op_ids = [o['op_id'] for o in data['operations']]
    assert _OPEN_AND_ENTER in op_ids


def test_handle_game_operations_describe() -> None:
    """GET /game/operations/describe?op_id= 返回参数 schema(op_id 走 query)。"""
    from zzz_od.backend.http.service_routes import handle_game_operations_describe

    backend = MagicMock()
    request = MagicMock()
    request.query_params = {'op_id': _MAP_TRANSPORT}
    resp = asyncio.run(handle_game_operations_describe(backend, request))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode('utf-8'))
    assert data['class_name'] == 'MapTransport'
    assert [p['name'] for p in data['params']] == ['area_name', 'tp_name']


def test_handle_game_operations_describe_missing_op_id() -> None:
    """无 op_id query → 200 + {error}。"""
    from zzz_od.backend.http.service_routes import handle_game_operations_describe

    backend = MagicMock()
    request = MagicMock()
    request.query_params = {}
    resp = asyncio.run(handle_game_operations_describe(backend, request))
    assert resp.status_code == 200
    assert 'error' in json.loads(resp.body.decode('utf-8'))


def test_handle_game_run_operation_op_id_via_query_args_via_body() -> None:
    """POST /game/run/operation:op_id 走 query、args 走 body;成功启动(_start 被调)。"""
    from zzz_od.backend.http.service_routes import handle_game_run_operation

    backend = MagicMock()
    backend.run_slot._start.return_value = (True, Future())
    backend.query_status.return_value = RunStatusResult(
        state='running', source='http', started_at='2026-07-02T00:00:00', duration_seconds=1.0)
    request = _request_with_body({'op_id': _OPEN_AND_ENTER, 'block': 'false'}, {'some': 'arg'})
    resp = asyncio.run(handle_game_run_operation(backend, request))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode('utf-8'))
    assert data['started'] is True
    backend.run_slot._start.assert_called_once()
    call = backend.run_slot._start.call_args
    assert call.args[0] == 'http'
    assert call.kwargs.get('display_name') == _OPEN_AND_ENTER


def test_handle_game_run_operation_rejects_non_operation() -> None:
    """op_id 非 Operation → 200 + {started: False, error}。"""
    from zzz_od.backend.http.service_routes import handle_game_run_operation

    backend = MagicMock()
    request = _request_with_body({'op_id': _CHARGE_PLAN_ITEM}, {})
    resp = asyncio.run(handle_game_run_operation(backend, request))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode('utf-8'))
    assert data['started'] is False and 'error' in data
    backend.run_slot._start.assert_not_called()


def test_handle_game_run_operation_rejects_missing_param() -> None:
    """缺必填参数(MapTransport.tp_name)→ 200 + {started: False, error}。"""
    from zzz_od.backend.http.service_routes import handle_game_run_operation

    backend = MagicMock()
    request = _request_with_body({'op_id': _MAP_TRANSPORT}, {'area_name': '六分街'})
    resp = asyncio.run(handle_game_run_operation(backend, request))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode('utf-8'))
    assert data['started'] is False
    assert 'tp_name' in data['error']


def test_handle_game_run_operation_concurrent_reject() -> None:
    """单跑道已有运行 → 200 + {started: False, source}。"""
    from zzz_od.backend.http.service_routes import handle_game_run_operation

    backend = MagicMock()
    backend.run_slot._start.return_value = (False, None)
    backend.query_status.return_value = RunStatusResult(state='running', source='mcp')
    request = _request_with_body({'op_id': _OPEN_AND_ENTER}, {})
    resp = asyncio.run(handle_game_run_operation(backend, request))
    data = json.loads(resp.body.decode('utf-8'))
    assert data['started'] is False
    assert data['error'] == '已有运行在进行中'
    assert data['source'] == 'mcp'


def test_register_service_routes_adds_operation_routes() -> None:
    """register_http_routes 应挂载 /game/operations 系列端点。"""
    from mcp.server.fastmcp import FastMCP

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP('test')
    register_http_routes(mcp, MagicMock())
    app = mcp.streamable_http_app()
    paths = {getattr(r, 'path', None) for r in app.routes}
    assert '/game/operations' in paths
    assert '/game/operations/describe' in paths
    assert '/game/run/operation' in paths
