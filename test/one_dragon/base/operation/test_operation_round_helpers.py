"""Operation ``round_by_*`` helper 返回契约测试（框架层，一次测全）。

薄包装节点（``return self.round_by_X(...)``）的分支 = helper 的返回契约。
这里在框架层把每个 helper 的每种返回各测一次，app 层的薄包装节点就不需要再逐个
重复验证 helper 本身的行为，只需关心传入的画面 / 区域 / 目标词是否正确。

不依赖真实 OCR / 截图 / 配置：
- ``screen_utils.find_area`` / ``find_area_binary`` / ``find_and_click_area`` / ``find_by_ocr`` /
  ``get_match_screen_name`` 用 monkeypatch 替换为预设返回；
- ``ctx`` 为 :class:`_FakeCtx`，只提供 helper 用到的 ``screen_loader`` / ``controller`` / ``ocr_service``；
- ``time.sleep`` 替换为记录调用，不真等待。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation import operation as operation_module
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, OcrClickResultEnum

SUCCESS = OperationRoundResultEnum.SUCCESS
WAIT = OperationRoundResultEnum.WAIT
RETRY = OperationRoundResultEnum.RETRY
FAIL = OperationRoundResultEnum.FAIL


# --------------------------------------------------------------------------- #
# 假上下文
# --------------------------------------------------------------------------- #


def _make_area(goto_list: list[str] | None = None) -> SimpleNamespace:
    """构造 helper 会用到的 ScreenArea 字段。"""
    return SimpleNamespace(
        center=Point(50, 60),
        left_top=Point(10, 20),
        pc_alt=False,
        gamepad_key=None,
        color_range=None,
        rect=None,
        goto_list=goto_list,
    )


class _FakeScreenLoader:

    def __init__(self) -> None:
        self.area_map: dict[tuple[str, str], SimpleNamespace] = {}
        self.route_map: dict[tuple[str, str], Any] = {}
        self.current_screen_name_list: list[str | None] = []

    def get_area(self, screen_name: str, area_name: str) -> SimpleNamespace | None:
        return self.area_map.get((screen_name, area_name))

    def get_screen_route(self, from_screen: str, to_screen: str) -> Any:
        return self.route_map.get((from_screen, to_screen))

    def update_current_screen_name(self, screen_name: str | None) -> None:
        self.current_screen_name_list.append(screen_name)


class _FakeController:

    def __init__(self) -> None:
        self.click_result: bool = True
        self.click_list: list[Point] = []

    def click(self, pos: Point, pc_alt: bool = False, gamepad_key: Any = None) -> bool:
        self.click_list.append(pos)
        return self.click_result


class _FakeOcrService:

    def __init__(self) -> None:
        self.result_map: dict[str, MatchResultList] = {}

    def get_ocr_result_map(self, image: Any, rect: Any = None, color_range: Any = None,
                           crop_first: bool = True) -> dict[str, MatchResultList]:
        return dict(self.result_map)


class _FakeCtx:

    def __init__(self) -> None:
        self.screen_loader: _FakeScreenLoader = _FakeScreenLoader()
        self.controller: _FakeController = _FakeController()
        self.ocr_service: _FakeOcrService = _FakeOcrService()


def _mrl(x: int, y: int, w: int = 20, h: int = 10) -> MatchResultList:
    mrl = MatchResultList()
    mrl.append(MatchResult(1, x, y, w, h))
    return mrl


@pytest.fixture
def ctx() -> _FakeCtx:
    return _FakeCtx()


@pytest.fixture
def op(ctx: _FakeCtx) -> Operation:
    o = Operation(ctx, op_name='helper契约测试')  # type: ignore[arg-type]
    o.last_screenshot = object()  # helper 只透传截图，不读内容
    return o


@pytest.fixture
def sleep_calls(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    calls: list[float] = []
    monkeypatch.setattr(operation_module.time, 'sleep', lambda s: calls.append(s))
    return calls


# --------------------------------------------------------------------------- #
# _after_round_wait：wait 优先于 wait_round_time
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ('wait', 'wait_round_time', 'elapsed', 'expected'),
    [
        (None, None, 0, []),
        (0.5, 2, 0, [0.5]),  # wait 优先
        (0, None, 0, []),  # wait=0 视为不等
        (None, 2, 0.5, [1.5]),  # 补足轮次时间
        (None, 2, 3, []),  # 轮次已超时 不等
    ],
    ids=['不等待', 'wait优先', 'wait为0', '补足轮次时间', '轮次已超时'],
)
def test_after_round_wait(op: Operation, sleep_calls: list[float], monkeypatch: pytest.MonkeyPatch,
                          wait: float | None, wait_round_time: float | None,
                          elapsed: float, expected: list[float]) -> None:
    monkeypatch.setattr(operation_module.time, 'time', lambda: 100 + elapsed)
    op.round_start_time = 100
    op.round_success(wait=wait, wait_round_time=wait_round_time)
    assert sleep_calls == pytest.approx(expected)


# --------------------------------------------------------------------------- #
# round_by_op_result
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ('success', 'retry_on_fail', 'status', 'expected_result', 'expected_status'),
    [
        (True, False, None, SUCCESS, '子op状态'),
        (True, True, '覆盖', SUCCESS, '覆盖'),
        (False, True, None, RETRY, '子op状态'),
        (False, False, '覆盖', FAIL, '覆盖'),
    ],
    ids=['成功透传status', '成功覆盖status', '失败重试', '失败覆盖status'],
)
def test_round_by_op_result(op: Operation, success: bool, retry_on_fail: bool, status: str | None,
                            expected_result: OperationRoundResultEnum, expected_status: str) -> None:
    result = op.round_by_op_result(OperationResult(success, '子op状态', data=1),
                                   status=status, retry_on_fail=retry_on_fail)
    assert result.result == expected_result
    assert result.status == expected_status
    assert result.data == 1


# --------------------------------------------------------------------------- #
# round_by_find_and_click_area
# --------------------------------------------------------------------------- #


def test_find_and_click_area_missing_param(op: Operation) -> None:
    result = op.round_by_find_and_click_area(screen_name='画面', area_name=None)
    assert result.result == FAIL
    assert result.status == '未指定画面区域'


@pytest.mark.parametrize(
    ('click', 'expected_result', 'expected_status', 'expected_clicked'),
    [
        (OcrClickResultEnum.OCR_CLICK_SUCCESS, SUCCESS, '按钮', True),
        (OcrClickResultEnum.OCR_CLICK_NOT_FOUND, RETRY, '未找到 按钮', False),
        (OcrClickResultEnum.OCR_CLICK_FAIL, RETRY, '点击失败 按钮', False),
        (OcrClickResultEnum.AREA_NO_CONFIG, FAIL, '区域未配置 按钮', False),
    ],
    ids=['点击成功', '未找到', '点击失败', '区域未配置'],
)
def test_find_and_click_area_without_until(
        op: Operation, ctx: _FakeCtx, sleep_calls: list[float], monkeypatch: pytest.MonkeyPatch,
        click: OcrClickResultEnum, expected_result: OperationRoundResultEnum,
        expected_status: str, expected_clicked: bool) -> None:
    ctx.screen_loader.area_map[('画面', '按钮')] = _make_area(goto_list=['下一画面'])
    monkeypatch.setattr(screen_utils, 'find_and_click_area', lambda **kwargs: click)

    result = op.round_by_find_and_click_area(screen_name='画面', area_name='按钮')

    assert result.result == expected_result
    assert result.status == expected_status
    assert op.node_clicked == expected_clicked
    # 点击成功后按 goto_list 更新当前画面
    assert ctx.screen_loader.current_screen_name_list == (['下一画面'] if expected_clicked else [])


def _patch_find_area(monkeypatch: pytest.MonkeyPatch, found_area_set: set[str]) -> None:
    def fake_find_area(**kwargs: Any) -> FindAreaResultEnum:
        return FindAreaResultEnum.TRUE if kwargs['area_name'] in found_area_set else FindAreaResultEnum.FALSE

    monkeypatch.setattr(screen_utils, 'find_area', fake_find_area)


@pytest.mark.parametrize(
    ('until_key', 'node_clicked', 'found_area_set', 'expected_result', 'expect_click'),
    [
        # until_find_all：点击后等目标全部出现
        ('until_find_all', False, {'目标1', '目标2'}, WAIT, True),  # 首轮必须先点
        ('until_find_all', True, {'目标1', '目标2'}, SUCCESS, False),  # 已点且全出现 → 成功 不再点
        ('until_find_all', True, {'目标1'}, WAIT, True),  # 已点但未全出现 → 再点
        # until_not_find_all：点击后等目标全部消失
        ('until_not_find_all', True, set(), SUCCESS, False),  # 已点且全消失 → 成功
        ('until_not_find_all', True, {'目标2'}, WAIT, True),  # 仍有目标 → 再点
    ],
    ids=['find_all-首轮点击', 'find_all-全出现', 'find_all-部分出现',
         'not_find_all-全消失', 'not_find_all-仍存在'],
)
def test_find_and_click_area_with_until(
        op: Operation, ctx: _FakeCtx, sleep_calls: list[float], monkeypatch: pytest.MonkeyPatch,
        until_key: str, node_clicked: bool, found_area_set: set[str],
        expected_result: OperationRoundResultEnum, expect_click: bool) -> None:
    ctx.screen_loader.area_map[('画面', '按钮')] = _make_area()
    _patch_find_area(monkeypatch, found_area_set)
    click_calls: list[str] = []

    def fake_click(**kwargs: Any) -> OcrClickResultEnum:
        click_calls.append(kwargs['area_name'])
        return OcrClickResultEnum.OCR_CLICK_SUCCESS

    monkeypatch.setattr(screen_utils, 'find_and_click_area', fake_click)
    op.node_clicked = node_clicked

    result = op.round_by_find_and_click_area(
        screen_name='画面', area_name='按钮',
        **{until_key: [('画面', '目标1'), ('画面', '目标2')]},
    )

    assert result.result == expected_result
    assert result.status == '按钮'
    assert click_calls == (['按钮'] if expect_click else [])


# --------------------------------------------------------------------------- #
# round_by_find_area / round_by_find_area_binary（契约相同）
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ('helper_name', 'patch_name'),
    [('round_by_find_area', 'find_area'), ('round_by_find_area_binary', 'find_area_binary')],
)
@pytest.mark.parametrize(
    ('find_result', 'expected_result', 'expected_status'),
    [
        (FindAreaResultEnum.TRUE, SUCCESS, '区域'),
        (FindAreaResultEnum.FALSE, RETRY, '未找到 区域'),
        (FindAreaResultEnum.AREA_NO_CONFIG, FAIL, '区域未配置 区域'),
    ],
    ids=['找到', '未找到', '区域未配置'],
)
def test_find_area(op: Operation, monkeypatch: pytest.MonkeyPatch, helper_name: str, patch_name: str,
                   find_result: FindAreaResultEnum, expected_result: OperationRoundResultEnum,
                   expected_status: str) -> None:
    monkeypatch.setattr(screen_utils, patch_name, lambda **kwargs: find_result)
    result = getattr(op, helper_name)(op.last_screenshot, '画面', '区域')
    assert result.result == expected_result
    assert result.status == expected_status


# --------------------------------------------------------------------------- #
# round_by_click_area
# --------------------------------------------------------------------------- #


def test_click_area_no_config(op: Operation, ctx: _FakeCtx) -> None:
    result = op.round_by_click_area('画面', '区域')
    assert result.result == FAIL
    assert result.status == '区域未配置 区域'
    assert ctx.controller.click_list == []


@pytest.mark.parametrize(
    ('click_result', 'click_left_top', 'expected_result', 'expected_status', 'expected_pos'),
    [
        (True, False, SUCCESS, '区域', Point(50, 60)),
        (True, True, SUCCESS, '区域', Point(10, 20)),
        (False, False, RETRY, '点击失败 区域', Point(50, 60)),
    ],
    ids=['点击中心', '点击左上角', '点击失败'],
)
def test_click_area(op: Operation, ctx: _FakeCtx, sleep_calls: list[float],
                    click_result: bool, click_left_top: bool,
                    expected_result: OperationRoundResultEnum, expected_status: str, expected_pos: Point) -> None:
    ctx.screen_loader.area_map[('画面', '区域')] = _make_area(goto_list=['下一画面'])
    ctx.controller.click_result = click_result

    result = op.round_by_click_area('画面', '区域', click_left_top=click_left_top)

    assert result.result == expected_result
    assert result.status == expected_status
    assert [(p.x, p.y) for p in ctx.controller.click_list] == [(expected_pos.x, expected_pos.y)]
    assert ctx.screen_loader.current_screen_name_list == (['下一画面'] if click_result else [])


# --------------------------------------------------------------------------- #
# round_by_ocr_and_click
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ('ocr_map', 'click_result', 'kwargs', 'expected_result', 'expected_status', 'expected_click'),
    [
        ({'确认': _mrl(0, 0)}, True, {}, SUCCESS, '确认', (10, 5)),
        ({'确认': _mrl(0, 0)}, True, {'offset': Point(1, 2)}, SUCCESS, '确认', (11, 7)),
        ({'取消': _mrl(0, 0)}, True, {}, RETRY, '找不到 确认', None),
        ({'确认': MatchResultList()}, True, {}, RETRY, '找不到 确认', None),  # 无坐标的结果被忽略
        ({'确认': _mrl(0, 0)}, False, {}, RETRY, '点击 确认 失败', (10, 5)),
    ],
    ids=['命中', '命中加偏移', '未命中', '结果无坐标', '点击失败'],
)
def test_ocr_and_click(op: Operation, ctx: _FakeCtx, sleep_calls: list[float],
                       ocr_map: dict[str, MatchResultList], click_result: bool, kwargs: dict[str, Any],
                       expected_result: OperationRoundResultEnum, expected_status: str,
                       expected_click: tuple[int, int] | None) -> None:
    ctx.ocr_service.result_map = ocr_map
    ctx.controller.click_result = click_result

    result = op.round_by_ocr_and_click(op.last_screenshot, '确认', **kwargs)

    assert result.result == expected_result
    assert result.status == expected_status
    assert [(p.x, p.y) for p in ctx.controller.click_list] == ([expected_click] if expected_click else [])


def test_ocr_and_click_remove_whitespace(op: Operation, ctx: _FakeCtx, sleep_calls: list[float]) -> None:
    ctx.ocr_service.result_map = {'开 始 战 斗': _mrl(0, 0)}
    assert op.round_by_ocr_and_click(op.last_screenshot, '开始战斗', remove_whitespace=True).is_success


# --------------------------------------------------------------------------- #
# round_by_ocr_and_click_by_priority
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ('ocr_map', 'ignore_list', 'expected_result', 'expected_status', 'expected_click'),
    [
        ({'领取': _mrl(0, 0), '前往': _mrl(100, 0)}, None, SUCCESS, '前往', (110, 5)),  # 按列表优先级
        ({'领取': _mrl(0, 0)}, None, SUCCESS, '领取', (10, 5)),
        ({'已领取': _mrl(0, 0)}, ['已领取'], RETRY, '未匹配到目标文本', None),  # 忽略词不返回
        ({'其他': _mrl(0, 0)}, None, RETRY, '未匹配到目标文本', None),
    ],
    ids=['高优先级命中', '低优先级命中', '命中忽略词', '未命中'],
)
def test_ocr_and_click_by_priority(op: Operation, ctx: _FakeCtx, sleep_calls: list[float],
                                   ocr_map: dict[str, MatchResultList], ignore_list: list[str] | None,
                                   expected_result: OperationRoundResultEnum, expected_status: str,
                                   expected_click: tuple[int, int] | None) -> None:
    ctx.ocr_service.result_map = ocr_map

    result = op.round_by_ocr_and_click_by_priority(['前往', '已领取', '领取'], ignore_cn_list=ignore_list)

    assert result.result == expected_result
    assert result.status == expected_status
    assert [(p.x, p.y) for p in ctx.controller.click_list] == ([expected_click] if expected_click else [])


# --------------------------------------------------------------------------- #
# round_by_ocr_and_click_with_action
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ('ocr_word', 'expected_result', 'expected_status'),
    [
        ('出战', SUCCESS, '出战'),
        ('下一步', WAIT, '下一步'),
        ('重试', RETRY, '重试'),
        ('其他', RETRY, '未匹配到目标文本'),
    ],
    ids=['SUCCESS动作', 'WAIT动作', 'RETRY动作', '未命中'],
)
def test_ocr_and_click_with_action(op: Operation, ctx: _FakeCtx, sleep_calls: list[float], ocr_word: str,
                                   expected_result: OperationRoundResultEnum, expected_status: str) -> None:
    ctx.ocr_service.result_map = {ocr_word: _mrl(0, 0)}

    result = op.round_by_ocr_and_click_with_action([
        ('出战', SUCCESS),
        ('下一步', WAIT),
        ('重试', RETRY),
    ])

    assert result.result == expected_result
    assert result.status == expected_status
    assert len(ctx.controller.click_list) == (0 if ocr_word == '其他' else 1)


# --------------------------------------------------------------------------- #
# round_by_ocr
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ('found', 'expected_result', 'expected_status'),
    [(True, SUCCESS, '确认'), (False, RETRY, '找不到 确认')],
    ids=['找到', '未找到'],
)
def test_ocr(op: Operation, monkeypatch: pytest.MonkeyPatch, found: bool,
             expected_result: OperationRoundResultEnum, expected_status: str) -> None:
    monkeypatch.setattr(screen_utils, 'find_by_ocr', lambda *args, **kwargs: found)
    result = op.round_by_ocr(op.last_screenshot, '确认')
    assert result.result == expected_result
    assert result.status == expected_status


# --------------------------------------------------------------------------- #
# round_by_goto_screen（不含防抖分支）
# --------------------------------------------------------------------------- #


def _route(from_area: str, to_screen: str) -> SimpleNamespace:
    return SimpleNamespace(can_go=True, node_list=[SimpleNamespace(from_area=from_area, to_screen=to_screen)])


@pytest.mark.parametrize(
    ('current_screen', 'route', 'click', 'expected_result', 'expected_status', 'expected_current'),
    [
        (None, None, None, RETRY, Operation.STATUS_SCREEN_UNKNOWN, [None]),
        ('目标', None, None, SUCCESS, '目标', ['目标']),
        ('当前', None, None, FAIL, '无法从 当前 前往 目标', ['当前']),
        ('当前', SimpleNamespace(can_go=False, node_list=[]), None, FAIL, '无法从 当前 前往 目标', ['当前']),
        ('当前', _route('按钮', '中转'), OcrClickResultEnum.OCR_CLICK_SUCCESS, WAIT, '按钮', ['当前', '中转']),
        ('当前', _route('按钮', '中转'), OcrClickResultEnum.OCR_CLICK_NOT_FOUND, RETRY, '未找到 按钮', ['当前']),
    ],
    ids=['画面未知', '已在目标', '无路由', '路由不可达', '点击路由按钮', '路由按钮未找到'],
)
def test_goto_screen(op: Operation, ctx: _FakeCtx, sleep_calls: list[float], monkeypatch: pytest.MonkeyPatch,
                     current_screen: str | None, route: Any, click: OcrClickResultEnum | None,
                     expected_result: OperationRoundResultEnum, expected_status: str,
                     expected_current: list[str | None]) -> None:
    monkeypatch.setattr(screen_utils, 'get_match_screen_name', lambda ctx, screen: current_screen)
    if route is not None:
        ctx.screen_loader.route_map[('当前', '目标')] = route
    ctx.screen_loader.area_map[('当前', '按钮')] = _make_area()
    monkeypatch.setattr(screen_utils, 'find_and_click_area', lambda **kwargs: click)

    result = op.round_by_goto_screen(screen_name='目标')

    assert result.result == expected_result
    assert result.status == expected_status
    assert ctx.screen_loader.current_screen_name_list == expected_current
