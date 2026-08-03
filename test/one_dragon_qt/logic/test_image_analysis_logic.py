# coding: utf-8
from unittest.mock import MagicMock

from one_dragon_qt.logic.image_analysis_logic import ImageAnalysisLogic


def _create_logic() -> ImageAnalysisLogic:
    """创建一个使用 mock cv_service 的 ImageAnalysisLogic，不触碰真实文件"""
    ctx = MagicMock()
    ctx.cv_service = MagicMock()
    logic = ImageAnalysisLogic(ctx)
    logic.cv_service.get_pipeline_names.return_value = []
    logic.cv_service.save_pipeline.return_value = True
    return logic


def test_auto_save_pipeline_generates_first_name():
    """没有已保存流水线时，自动保存为「流水线1」"""
    logic = _create_logic()

    name = logic.auto_save_pipeline()

    assert name == '流水线1'
    assert logic.active_pipeline_name == '流水线1'
    logic.cv_service.save_pipeline.assert_called_once_with('流水线1', logic.pipeline)


def test_auto_save_pipeline_skips_existing_names():
    """已存在「流水线1」「流水线2」时，自动保存为「流水线3」，不覆盖已有文件"""
    logic = _create_logic()
    logic.cv_service.get_pipeline_names.return_value = ['流水线1', '流水线2']

    name = logic.auto_save_pipeline()

    assert name == '流水线3'
    assert logic.active_pipeline_name == '流水线3'


def test_auto_save_pipeline_save_failed():
    """保存失败时返回 None，且不修改当前激活的流水线名称"""
    logic = _create_logic()
    logic.active_pipeline_name = None
    logic.cv_service.save_pipeline.return_value = False

    name = logic.auto_save_pipeline()

    assert name is None
    assert logic.active_pipeline_name is None
