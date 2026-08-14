from unittest.mock import MagicMock, patch

import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_utils import (
    FindAreaResultEnum,
    OcrClickResultEnum,
    find_and_click_area,
    is_target_screen,
)


def _context_with_area(area: ScreenArea) -> MagicMock:
    ctx = MagicMock()
    ctx.screen_loader.get_area.return_value = area
    return ctx


def test_find_and_click_dynamic_text_does_not_match_or_click() -> None:
    area = ScreenArea(area_name='动态文本', area_type='text', pc_rect=Rect(0, 0, 10, 10))
    ctx = _context_with_area(area)

    result = find_and_click_area(ctx, np.zeros((10, 10, 3), dtype=np.uint8), '测试', '动态文本')

    assert result == OcrClickResultEnum.OCR_CLICK_NOT_FOUND
    ctx.ocr_service.get_ocr_result_list.assert_not_called()
    ctx.controller.click.assert_not_called()


def test_find_and_click_none_area_clicks_center_directly() -> None:
    area = ScreenArea(area_name='点击区域', area_type='none', pc_rect=Rect(0, 0, 10, 10))
    ctx = _context_with_area(area)

    result = find_and_click_area(ctx, np.zeros((10, 10, 3), dtype=np.uint8), '测试', '点击区域')

    assert result == OcrClickResultEnum.OCR_CLICK_SUCCESS
    args, kwargs = ctx.controller.click.call_args
    assert (args[0].x, args[0].y) == (area.center.x, area.center.y)
    assert kwargs == {'pc_alt': False, 'gamepad_key': None}


def test_is_target_screen_ignores_unmatchable_id_mark() -> None:
    dynamic_area = ScreenArea(
        area_name='动态文本',
        area_type='text',
        pc_rect=Rect(0, 0, 10, 10),
        id_mark=True,
    )
    title_area = ScreenArea(
        area_name='标题',
        area_type='text',
        pc_rect=Rect(0, 0, 10, 10),
        text='标题',
        id_mark=True,
    )
    ctx = MagicMock()
    screen = np.zeros((10, 10, 3), dtype=np.uint8)
    screen_info = MagicMock(area_list=[dynamic_area, title_area])

    with patch(
        'one_dragon.base.screen.screen_utils.find_area_in_screen',
        return_value=FindAreaResultEnum.TRUE,
    ) as find_area:
        result = is_target_screen(ctx, screen, screen_info=screen_info)

    assert result is True
    args = find_area.call_args.args
    assert args[0] is ctx
    assert args[1] is screen
    assert args[2] is title_area
    assert args[3] is True


def test_is_target_screen_requires_matchable_id_mark() -> None:
    dynamic_area = ScreenArea(
        area_name='动态文本',
        area_type='text',
        pc_rect=Rect(0, 0, 10, 10),
        id_mark=True,
    )
    ctx = MagicMock()
    screen_info = MagicMock(area_list=[dynamic_area])

    with patch('one_dragon.base.screen.screen_utils.find_area_in_screen') as find_area:
        result = is_target_screen(ctx, np.zeros((10, 10, 3), dtype=np.uint8), screen_info=screen_info)

    assert result is False
    find_area.assert_not_called()
