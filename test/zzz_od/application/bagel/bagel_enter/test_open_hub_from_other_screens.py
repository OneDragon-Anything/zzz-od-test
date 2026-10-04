from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.screen import screen_utils
from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_enter import BagelEnter

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_world_away_from_reception_uses_map_transport(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """普通大世界不要求先站在达塔面前，传送后再按画面确认入口。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.screenshot()
    monkeypatch.setattr(op, 'round_by_find_area', lambda *_args: op.round_retry())
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda *_args: '大世界-普通')
    monkeypatch.setattr(op, '_at_reception', lambda: False)
    transport = MagicMock(return_value=OperationResult(True, '传送完成'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    result = op.open_hub()
    assert not result.is_fail
    assert result.status == '等待研究站传送落地'
    transport.assert_called_once()


def test_wengine_warehouse_uses_map_transport(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """识别普通音擎仓库后经大世界传送。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.screenshot()
    monkeypatch.setattr(op, 'round_by_find_area', lambda *_args: op.round_retry())
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda *_args: '仓库-音擎仓库')
    monkeypatch.setattr(op, '_at_reception', lambda: False)
    transport = MagicMock(return_value=OperationResult(True, '传送完成'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    result = op.open_hub()
    assert not result.is_fail
    assert result.status == '等待研究站传送落地'
    transport.assert_called_once()


@pytest.mark.parametrize('missing_material_area', [False, True])
def test_wengine_warehouse_is_recognized_in_bagel_scope(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, missing_material_area: bool,
) -> None:
    """贝果应用画面范围不包含音擎仓库，入口按标题补认。"""
    image = (
        Path(__file__).resolve().parents[4]
        / 'one_dragon/base/screen/screen_loader/test_get_match_screen_name/storage_wengine.webp'
    )
    screen = cv2_utils.read_image(str(image))
    if missing_material_area:
        monkeypatch.delitem(test_context.screen_loader._screen_area_map, '仓库-材料道具.标题-材料道具')
    test_context.screen_loader.enter_scope('bagel')
    try:
        assert screen_utils.get_match_screen_name(test_context, screen) is None
        op = BagelEnter(test_context)
        op.last_screenshot = screen
        assert op._ordinary_warehouse() == '仓库-音擎仓库'
    finally:
        test_context.screen_loader.exit_scope()


def test_wengine_warehouse_without_global_match_uses_title(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全局画面匹配为未知时，只凭完整仓库标题进入已有传送流程。"""
    image = (
        Path(__file__).resolve().parents[4]
        / 'one_dragon/base/screen/screen_loader/test_get_match_screen_name/storage_wengine.webp'
    )
    op = BagelEnter(test_context)
    op.last_screenshot = cv2_utils.read_image(str(image))
    monkeypatch.setattr(op, '_at_reception', lambda: False)
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda *_args: None)
    transport = MagicMock(return_value=OperationResult(True, '传送完成'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    result = op.open_hub()
    assert not result.is_fail
    assert result.status == '等待研究站传送落地'
    transport.assert_called_once()
    assert test_context.screen_loader.current_screen_name == '仓库-音擎仓库'


@pytest.mark.parametrize('missing_warehouse_areas', [False, True])
def test_unknown_screen_never_transports_or_clicks(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, missing_warehouse_areas: bool,
) -> None:
    """无法识别的画面不尝试通用返回或地图传送。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.screenshot()
    if missing_warehouse_areas:
        for name in ('材料道具', '音擎仓库', '驱动仓库'):
            monkeypatch.delitem(test_context.screen_loader._screen_area_map, f'仓库-{name}.标题-{name}')
    monkeypatch.setattr(op, 'round_by_find_area', lambda *_args: op.round_retry())
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda *_args: None)
    transport = MagicMock()
    click = MagicMock()
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    monkeypatch.setattr(test_context.controller, 'click', click)
    result = op.open_hub()
    assert result.is_fail
    transport.assert_not_called()
    click.assert_not_called()


def test_other_gameplay_screen_is_left_untouched(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已识别的其他玩法局内也不能调用会退出战斗的通用传送。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.screenshot()
    monkeypatch.setattr(op, 'round_by_find_area', lambda *_args: op.round_retry())
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda *_args: '战斗画面')
    transport = MagicMock()
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    assert op.open_hub().is_fail
    transport.assert_not_called()


def test_transport_failure_is_reported_without_repeating(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """传送失败立即停，不重试有副作用的地图操作。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.screenshot()
    monkeypatch.setattr(op, 'round_by_find_area', lambda *_args: op.round_retry())
    monkeypatch.setattr(op, '_at_reception', lambda: False)
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda *_args: '菜单')
    transport = MagicMock(return_value=OperationResult(False, '未找到传送点'))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.Transport.execute', transport)
    result = op.open_hub()
    assert result.is_fail and result.status == '未找到传送点'
    assert not op.transport_started
    transport.assert_called_once()


def test_landing_without_reception_stops_without_interacting(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """传送成功不能代替落地后的达塔识别。"""
    test_context.mock_screen('贝果-局内', '高危A出生-原生1080')
    op = BagelEnter(test_context)
    op.screenshot()
    op.transport_started = True

    def find_area(_screen: object, _name: str, area: str) -> object:
        """模拟已落地但达塔提示缺失。"""
        return op.round_success() if area == '快捷手册' else op.round_retry()

    monkeypatch.setattr(op, 'round_by_find_area', find_area)
    monkeypatch.setattr(op, '_at_reception', lambda: False)
    interact = MagicMock()
    monkeypatch.setattr(test_context.controller, 'interact', interact)
    assert op.open_hub().is_fail
    interact.assert_not_called()
