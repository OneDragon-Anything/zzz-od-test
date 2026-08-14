from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea, ScreenAreaType
from one_dragon.base.screen.screen_info import ScreenInfo


def test_screen_area_type_values_and_legacy_aliases() -> None:
    assert ScreenAreaType.NONE == 'none'
    assert ScreenAreaType.TEXT == 'text'
    assert ScreenAreaType.TEMPLATE == 'template'
    assert ScreenArea(area_type='click').area_type == ScreenAreaType.NONE
    assert ScreenArea(area_type='ocr').area_type == ScreenAreaType.TEXT


def test_old_yaml_area_type_inference_uses_recognition_fields() -> None:
    text_area = ScreenArea(text='快捷手册')
    template_area = ScreenArea(template_id='back')
    plain_area = ScreenArea(color_range=[[208, 208, 208], [255, 255, 255]])

    assert text_area.area_type == ScreenAreaType.TEXT
    assert template_area.area_type == ScreenAreaType.TEMPLATE
    assert plain_area.area_type == ScreenAreaType.NONE


def test_text_color_range_is_serialized_as_text_parameter() -> None:
    color_range = [[230, 230, 230], [255, 255, 255]]
    area = ScreenArea(
        area_type='text',
        text='快捷手册',
        color_range=color_range,
    )

    data = area.to_dict()
    assert area.color_range == color_range
    assert data['color_range'] == color_range


def test_dynamic_text_area_keeps_type_parameters_but_cannot_match() -> None:
    color_range = [[208, 208, 208], [255, 255, 255]]
    area = ScreenArea(
        area_name='列表范围',
        area_type=ScreenAreaType.TEXT,
        pc_rect=Rect(1220, 35, 1770, 110),
        lcs_percent=0.5,
        color_range=color_range,
        id_mark=True,
    )

    assert area.is_text_area is True
    assert area.can_match is False
    data = area.to_dict()
    assert data['area_type'] == 'text'
    assert data['lcs_percent'] == 0.5
    assert data['color_range'] == color_range
    assert data['id_mark'] is True
    assert 'text' not in data


def test_current_type_default_thresholds_are_always_serialized() -> None:
    text_data = ScreenArea(area_type='text', text='标题', lcs_percent=0.5).to_dict()
    template_data = ScreenArea(
        area_type='template',
        template_sub_dir='menu',
        template_id='back',
        template_match_threshold=0.7,
    ).to_dict()

    assert text_data['lcs_percent'] == 0.5
    assert template_data['template_match_threshold'] == 0.7


def test_serialization_prunes_other_area_type_fields() -> None:
    area = ScreenArea(
        area_type='template',
        text='旧文本',
        lcs_percent=0.9,
        template_sub_dir='menu',
        template_id='back',
        template_match_threshold=0.7,
        color_range=[[1, 1, 1], [2, 2, 2]],
    )

    data = area.to_dict()
    assert data['template_sub_dir'] == 'menu'
    assert data['template_id'] == 'back'
    assert data['template_match_threshold'] == 0.7
    assert 'text' not in data
    assert 'lcs_percent' not in data
    assert 'color_range' not in data


def test_none_serialization_prunes_recognition_fields() -> None:
    data = ScreenArea(
        area_type='none',
        text='旧文本',
        lcs_percent=0.9,
        template_sub_dir='menu',
        template_id='back',
        template_match_threshold=0.8,
        color_range=[[1, 1, 1], [2, 2, 2]],
    ).to_dict()

    assert data['area_type'] == 'none'
    assert 'text' not in data
    assert 'lcs_percent' not in data
    assert 'color_range' not in data
    assert 'template_sub_dir' not in data
    assert 'template_id' not in data
    assert 'template_match_threshold' not in data


def test_screen_info_explicit_null_thresholds_fall_back_to_defaults() -> None:
    screen = ScreenInfo({
        'screen_id': 'test',
        'screen_name': '测试',
        'area_list': [
            {
                'area_name': '文本',
                'area_type': 'text',
                'pc_rect': [0, 0, 10, 10],
                'text': '标题',
                'lcs_percent': None,
            },
            {
                'area_name': '模板',
                'area_type': 'template',
                'pc_rect': [0, 0, 10, 10],
                'template_id': 'back',
                'template_match_threshold': None,
            },
        ],
    })

    assert screen.area_list[0].lcs_percent == 0.5
    assert screen.area_list[1].template_match_threshold == 0.7


def test_dynamic_text_round_trip_keeps_color_filter() -> None:
    original = ScreenArea(
        area_name='动态文本',
        area_type='text',
        pc_rect=Rect(1, 2, 30, 40),
        lcs_percent=0.5,
        color_range=[[10, 20, 30], [200, 210, 220]],
    )
    screen = ScreenInfo({
        'screen_id': 'test',
        'screen_name': '测试',
        'area_list': [original.to_dict()],
    })
    loaded = screen.area_list[0]

    assert loaded.area_type == ScreenAreaType.TEXT
    assert loaded.text == ''
    assert loaded.lcs_percent == 0.5
    assert loaded.color_range == original.color_range
    assert loaded.to_dict() == original.to_dict()
