from pathlib import Path

import yaml

from one_dragon.base.screen.screen_loader import ScreenContext


def test_motion_area_is_present_in_runtime_config(motion_screen_loader: ScreenContext) -> None:
    """默认加载的合并配置必须与源配置中的运动检测区域一致。"""
    area = motion_screen_loader.get_area('迷失之地-大世界', '区域-运动检测')
    assert area is not None
    source = yaml.safe_load(Path('assets/game_data/screen_info/lost_void_normal_world.yml').read_text(encoding='utf-8'))
    source_area = next(item for item in source['area_list'] if item['area_name'] == '区域-运动检测')
    assert [area.rect.x1, area.rect.y1, area.rect.x2, area.rect.y2] == source_area['pc_rect']
    assert not area.id_mark
