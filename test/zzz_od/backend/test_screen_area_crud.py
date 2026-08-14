from unittest.mock import MagicMock

from one_dragon.base.screen.screen_area import ScreenAreaType
from one_dragon.base.screen.screen_info import ScreenInfo
from zzz_od.backend.backend_context import ZzzBackendContext


def _backend_with_empty_screen() -> tuple[ZzzBackendContext, MagicMock, ScreenInfo]:
    ctx = MagicMock()
    screen = ScreenInfo({
        'screen_id': 'test',
        'screen_name': '测试画面',
        'area_list': [],
    })
    ctx.screen_loader.get_screen.return_value = screen
    return ZzzBackendContext(ctx), ctx, screen


def test_upsert_screen_area_keeps_dynamic_text_type_parameters() -> None:
    backend, ctx, screen = _backend_with_empty_screen()
    color_range = [[208, 208, 208], [255, 255, 255]]

    result = backend.upsert_screen_area(
        screen_name='测试画面',
        area_name='资源栏',
        pc_rect=[1, 2, 30, 40],
        area_type='text',
        color_range=color_range,
    )

    assert result['success'] is True
    assert result['action'] == 'inserted'
    area = screen.area_list[0]
    assert area.area_type == ScreenAreaType.TEXT
    assert area.can_match is False
    assert area.to_dict()['lcs_percent'] == 0.5
    assert area.to_dict()['color_range'] == color_range
    ctx.screen_loader.save_screen.assert_called_once_with(screen)


def test_upsert_screen_area_rejects_unmatchable_id_mark() -> None:
    backend, ctx, _screen = _backend_with_empty_screen()

    result = backend.upsert_screen_area(
        screen_name='测试画面',
        area_name='动态文本',
        pc_rect=[1, 2, 30, 40],
        area_type='text',
        id_mark=True,
    )

    assert result['success'] is False
    assert 'id_mark' in result['error']
    ctx.screen_loader.save_screen.assert_not_called()


def test_upsert_screen_area_ignores_template_fields_for_text_type() -> None:
    backend, ctx, screen = _backend_with_empty_screen()

    result = backend.upsert_screen_area(
        screen_name='测试画面',
        area_name='标题',
        pc_rect=[1, 2, 30, 40],
        area_type='text',
        text='标题',
        template_sub_dir='missing',
        template_id='missing',
    )

    assert result['success'] is True
    ctx.template_loader.load_template.assert_not_called()
    assert 'template_id' not in screen.area_list[0].to_dict()
