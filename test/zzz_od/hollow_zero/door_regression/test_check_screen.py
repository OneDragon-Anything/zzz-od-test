from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher, OnnxOcrParam
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.utils import cv2_utils
from zzz_od.hollow_zero.event.door_battle import DoorBattle


@pytest.mark.parametrize('model', ['ppocrv6', 'ppocrv5'])
def test_real_door_option(
    door_context: SimpleNamespace, door_image: Path, model: str,
) -> None:
    """使用真实截图及运行时裁剪、白色筛选参数，验证开门点击坐标。"""
    ctx = door_context
    ctx.ocr = OnnxOcrMatcher(OnnxOcrParam(ocr_model_name=model))
    assert ctx.ocr.init_model()
    op = DoorBattle(ctx)
    op.last_screenshot = cv2_utils.read_image(str(door_image))
    result = op.check_screen()
    assert result.is_success
    assert result.status == '开门'
    clicked = ctx.controller.click.call_args_list[0].args[0]
    assert 1390 <= clicked.x <= 1460
    assert 750 <= clicked.y <= 800


@pytest.mark.parametrize('option', ['接受检疫扫描', '使用共犯的钥匙扣', '强行闯入通道'])
def test_corruption_options(door_context: SimpleNamespace, option: str) -> None:
    """侵蚀门被识别为善战门时，仍可处理现有选项。"""
    ctx = door_context
    matches = MatchResultList()
    matches.append(MatchResult(1, 100, 200, 200, 40))
    ctx.ocr = Mock()
    ctx.ocr.run_ocr.side_effect = lambda _: {option: matches}
    op = DoorBattle(ctx)
    op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = op.check_screen()
    assert result.is_success
    assert result.status == option


def test_unknown_option_still_retries(door_context: SimpleNamespace) -> None:
    """未知画面不能被当作成功开门。"""
    ctx = door_context
    ctx.ocr = Mock()
    ctx.ocr.run_ocr.return_value = {}
    op = DoorBattle(ctx)
    op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = op.check_screen()
    assert result.result == OperationRoundResultEnum.RETRY
    assert result.status == '未匹配合适的处理方法'
