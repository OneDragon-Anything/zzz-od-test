"""TemplateInfo 保存模板原图 / 掩码的写盘结果（#2999 后续）。"""
import numpy as np
import pytest

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.geometry.point import Point
from one_dragon.base.screen import template_info as ti_module
from one_dragon.base.screen.template_info import TemplateInfo
from one_dragon.utils import cv2_utils

SCREEN = np.zeros((100, 120, 3), dtype=np.uint8)


@pytest.fixture
def template(tmp_path, monkeypatch) -> TemplateInfo:
    """指向临时目录的 TemplateInfo，避免往仓库 assets 里写东西。"""
    monkeypatch.setattr(ti_module, 'get_template_config_path', lambda *args: str(tmp_path / 'config.yml'))
    monkeypatch.setattr(ti_module, 'get_template_dir_path', lambda *args, **kwargs: str(tmp_path))
    monkeypatch.setattr(ti_module, 'get_template_raw_path', lambda *args: str(tmp_path / 'raw.png'))
    monkeypatch.setattr(ti_module, 'get_template_mask_path', lambda *args: str(tmp_path / 'mask.png'))
    monkeypatch.setattr(TemplateInfo, 'make_template_dir', lambda self: None)

    template = TemplateInfo('sub_dir', 'template_id')
    template.screen_image = SCREEN
    template.point_list = [Point(10, 10), Point(60, 60)]
    return template


class TestSaveTemplateImage:

    def test_save_raw_writes_crop(self, template: TemplateInfo, tmp_path) -> None:
        assert template.save_raw() is True
        saved = cv2_utils.read_image(str(tmp_path / 'raw.png'))
        assert saved is not None
        assert saved.shape[:2] == (50, 50)

    def test_save_mask_writes_mask(self, template: TemplateInfo, tmp_path) -> None:
        assert template.save_mask() is True
        saved = cv2_utils.read_image(str(tmp_path / 'mask.png'))
        assert saved is not None
        assert saved.ndim == 2

    def test_save_mask_skipped_when_auto_mask_off(self, template: TemplateInfo, tmp_path) -> None:
        template.auto_mask = False
        assert template.save_mask() is True
        assert not (tmp_path / 'mask.png').exists()

    def test_save_raw_returns_false_without_screen(self, template: TemplateInfo) -> None:
        template.screen_image = None
        assert template.save_raw() is False
        assert template.save_mask() is False

    def test_save_returns_false_when_write_fails(
        self,
        template: TemplateInfo,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(cv2_utils, 'save_image', lambda img, path: False)
        assert template.save_raw() is False
        assert template.save_mask() is False

    def test_save_config_still_writes_yml(self, template: TemplateInfo, tmp_path) -> None:
        template.save_config()
        yml = YamlOperator(str(tmp_path / 'config.yml'))
        assert yml.get('template_id') == 'template_id'
