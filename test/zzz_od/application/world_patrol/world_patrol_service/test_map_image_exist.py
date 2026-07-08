import glob
import os

import yaml

from test.conftest import TestContext

from one_dragon.utils import cv2_utils, os_utils


class TestMapImageExist:
    """大地图资产完整性:遍历 world_patrol 各区域目录的 road_mask 与 icon 模板。

    road_mask.png 是区域道路掩码(非 template 体系、无 TemplateInfo 封装),用 ``read_image``;
    icon.yml 引用的 ``map`` 模板走 ``template_loader.get_template``(上层)。
    """

    def _wp_dir(self) -> str:
        return os_utils.get_path_under_work_dir('assets', 'game_data', 'world_patrol')

    def test_road_mask(self):
        """每个区域的道路掩码图能读(read_image 非 None)。"""
        road_masks = glob.glob(os.path.join(self._wp_dir(), '**', 'road_mask.png'), recursive=True)
        assert road_masks, '未找到任何 road_mask.png(world_patrol 目录结构变了?)'
        missing = [p for p in road_masks if cv2_utils.read_image(p) is None]
        assert not missing, f'road_mask 读失败: {missing}'

    def test_map_icon(self, test_context: TestContext):
        """每个 icon.yml 引用的 map 模板都能读到。"""
        icon_ymls = glob.glob(os.path.join(self._wp_dir(), '**', 'icon.yml'), recursive=True)
        missing = []
        for yml_path in icon_ymls:
            with open(yml_path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
            icons = data if isinstance(data, list) else []
            for icon in icons:
                tid = icon.get('template_id') if isinstance(icon, dict) else None
                if not tid:
                    continue
                template = test_context.template_loader.get_template('map', tid)
                if template is None or template.raw is None:
                    missing.append(f'{yml_path} → map/{tid}')
        assert not missing, f'缺失大地图图标模板: {missing}'
