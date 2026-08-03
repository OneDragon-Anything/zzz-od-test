# coding: utf-8
"""CvService 多目录来源解析 + cvpipe 拿框方法的单元测试（全部 mock，不落盘）"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from one_dragon.base.cv_process.cv_service import (
    CvService,
    reset_current_plugin,
    set_current_plugin,
)
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_utils import find_area_box


def _create_service() -> CvService:
    """创建 mock 上下文的 CvService，插件流水线目录可注入"""
    ctx = MagicMock()
    ctx.application_plugin_dirs = []
    service = CvService(ctx)
    # 模拟一个插件流水线目录：插件名 test_plugin
    service._plugin_pipeline_dirs = [('test_plugin', '/fake/plugins/test_plugin/assets/image_analysis_pipelines')]
    return service


def _mock_pipeline_context(rects: list[tuple[int, int, int, int]]):
    """构造返回指定轮廓框的流水线上下文 mock"""
    ctx = MagicMock()
    ctx.is_success = True
    ctx.get_absolute_rects.return_value = rects
    return ctx


# ==================== CvService 多目录 / 来源解析 ====================

def test_get_pipeline_names_by_source():
    """按来源过滤：主仓与插件分别返回自己的裸名列表，不混排"""
    service = _create_service()
    with patch('os.listdir', side_effect=[['a.yml', 'b.yml'], ['b.yml', 'c.yml']]):
        with patch('os.path.isdir', return_value=True):
            main_names = service.get_pipeline_names('')
            plugin_names = service.get_pipeline_names('test_plugin')

    assert main_names == ['a', 'b']
    assert plugin_names == ['b', 'c']


def test_load_pipeline_by_explicit_source():
    """显式 source 加载：插件名只查插件目录"""
    service = _create_service()
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', MagicMock()), \
         patch('one_dragon.base.cv_process.cv_service.yaml_utils.safe_load', return_value=None):
        pipeline = service.load_pipeline('b', source='test_plugin')
    assert pipeline is not None


def test_load_pipeline_bare_name_plugin_context_first():
    """裸名 + 插件上下文：优先解析自身插件目录，其次主仓"""
    service = _create_service()
    calls = []

    def fake_exists(path):
        calls.append(path)
        # 插件目录里的文件存在，主仓不存在 → 应命中插件
        return 'test_plugin' in str(path)

    with patch('os.path.exists', side_effect=fake_exists), \
         patch('builtins.open', MagicMock()), \
         patch('one_dragon.base.cv_process.cv_service.yaml_utils.safe_load', return_value=None):
        token = set_current_plugin('test_plugin')
        try:
            pipeline = service.load_pipeline('b')
        finally:
            reset_current_plugin(token)

    assert pipeline is not None
    assert any('test_plugin' in c for c in calls), '应优先查插件目录'


def test_load_pipeline_bare_name_main_when_no_plugin_context():
    """裸名 + 主仓上下文：直接查主仓目录"""
    service = _create_service()
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', MagicMock()), \
         patch('one_dragon.base.cv_process.cv_service.yaml_utils.safe_load', return_value=None):
        pipeline = service.load_pipeline('a')
    assert pipeline is not None


def test_save_pipeline_to_plugin():
    """保存到插件来源：写入插件目录"""
    service = _create_service()
    with patch('builtins.open', MagicMock()) as mock_open:
        ok = service.save_pipeline('c', MagicMock(), source='test_plugin')
    assert ok is True
    opened_path = mock_open.call_args[0][0]
    assert 'test_plugin' in opened_path


# ==================== cvpipe 拿框方法 ====================

def _create_cvpipe_area() -> ScreenArea:
    """构造 cvpipe 区域：pc_rect 偏移 (100, 200)，流水线输出裁剪图内轮廓框"""
    return ScreenArea(
        area_name='测试',
        pc_rect=Rect(100, 200, 500, 600),
        text='确定',
        cvpipe='电量检测',
    )


def test_find_area_box_cvpipe_coord_synthesis():
    """cvpipe 拿框：cv 框坐标 + pc_rect 偏移合成真实坐标"""
    area = _create_cvpipe_area()
    ctx = MagicMock()
    # 流水线在裁剪图上输出轮廓框 (10, 20, 50, 60)
    ctx.cv_service.run_pipeline.return_value = _mock_pipeline_context([(10, 20, 50, 60)])
    # 框内 OCR 匹配成功（text='确定'）
    ocr_result = MagicMock()
    ocr_result.data = '确定'
    ctx.ocr_service.get_ocr_result_list.return_value = [ocr_result]

    box = find_area_box(ctx, np.zeros((1080, 1920, 3), dtype=np.uint8), area)

    assert box == (110, 220, 150, 260), f'合成坐标错误: {box}'


def test_find_area_box_cvpipe_verify_each_box_first_hit():
    """cvpipe 拿框：多个候选框逐个验证，第一个命中立即返回"""
    area = _create_cvpipe_area()
    ctx = MagicMock()
    # 两个候选框：第一个框内 OCR 不匹配，第二个匹配
    ctx.cv_service.run_pipeline.return_value = _mock_pipeline_context([(10, 20, 50, 60), (70, 80, 120, 130)])

    def fake_ocr(image, rect, color_range, crop_first):
        # 第一个框 (110,220,150,260) 返回不匹配文字；第二个框返回「确定」
        if rect.x1 == 110:
            return [MagicMock(data='其他')]
        return [MagicMock(data='确定')]

    ctx.ocr_service.get_ocr_result_list.side_effect = fake_ocr

    box = find_area_box(ctx, np.zeros((1080, 1920, 3), dtype=np.uint8), area)

    assert box == (170, 280, 220, 330), f'应返回第二个命中框: {box}'


def test_find_area_box_cvpipe_all_fail_returns_none():
    """cvpipe 拿框：所有候选框验证失败返回 None（拿框可能为空）"""
    area = _create_cvpipe_area()
    ctx = MagicMock()
    ctx.cv_service.run_pipeline.return_value = _mock_pipeline_context([(10, 20, 50, 60)])
    ctx.ocr_service.get_ocr_result_list.return_value = [MagicMock(data='其他')]

    box = find_area_box(ctx, np.zeros((1080, 1920, 3), dtype=np.uint8), area)

    assert box is None


def test_find_area_box_cvpipe_pipeline_fail_returns_none():
    """cvpipe 拿框：流水线执行失败返回 None"""
    area = _create_cvpipe_area()
    ctx = MagicMock()
    failed_ctx = MagicMock()
    failed_ctx.is_success = False
    ctx.cv_service.run_pipeline.return_value = failed_ctx

    box = find_area_box(ctx, np.zeros((1080, 1920, 3), dtype=np.uint8), area)

    assert box is None
