"""LostVoidLottery.click_start 剩余次数分支测试。

按 testing methodology 动作一:``click_start`` OCR「文本-剩余次数」后按剩余次数分支:
- OCR 空 / 解析不到正数 / 解析到 0 → ``STATUS_NO_TIMES_LEFT``(不点击)。
- 解析到 >0 → 点击「按钮-开始」,返回 ``round_by_find_and_click_area`` 的结果。

源码行为(已读 ``lost_void_lottery.py`` 的 ``click_start`` 确认):
- ``ocr_result_map`` 为空(dict) → 直接 ``round_success(STATUS_NO_TIMES_LEFT)``。
- 遍历 OCR key,``str_utils.get_positive_digits(word, err=0)`` 为 ``None`` 或 ``0`` 时不算有效;
  任一 key 解析到 >0 即 ``is_valid=True``。
- ``is_valid`` 为 False → ``round_success(STATUS_NO_TIMES_LEFT)``。
- ``is_valid`` 为 True → 点击「按钮-开始」,命中按钮时返回 ``round_success(status='按钮-开始')``。

测法:用 patch ``ctx.ocr.crop_and_run_ocr`` 返回固定 OCR 结果覆盖三个分支(空 / '0' / >0),
确定性 GREEN;另用真实 fixture(``抽奖前.webp``)验证整条 >0 分支端到端 GREEN。
"""
from unittest.mock import patch

from test.conftest import TestContext

from one_dragon.base.matcher.match_result import MatchResultList
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_lottery import (
    LostVoidLottery,
)


def _setup_and_screenshot(test_context: TestContext, state: str) -> LostVoidLottery:
    """构造 op,装载 fixture 截图(供 OCR/模板识别在真实 fixture 用例下走通)。"""
    op = LostVoidLottery(test_context)
    test_context.mock_screen('迷失之地-抽奖机', state)
    op.screenshot()
    return op


def test_no_times_left_when_ocr_empty(test_context: TestContext) -> None:
    """OCR 返回空 dict → STATUS_NO_TIMES_LEFT(不点击)。"""
    op = _setup_and_screenshot(test_context, '抽奖前')
    with patch.object(test_context.ocr, 'crop_and_run_ocr', return_value={}):
        result = op.click_start()
    assert result.is_success
    assert result.status == LostVoidLottery.STATUS_NO_TIMES_LEFT


def test_no_times_left_when_zero(test_context: TestContext) -> None:
    """OCR 识别到 '0'(get_positive_digits 返回 0,非 >0)→ STATUS_NO_TIMES_LEFT。"""
    op = _setup_and_screenshot(test_context, '抽奖前')
    mock_map = {'0': MatchResultList()}
    with patch.object(test_context.ocr, 'crop_and_run_ocr', return_value=mock_map):
        result = op.click_start()
    assert result.is_success
    assert result.status == LostVoidLottery.STATUS_NO_TIMES_LEFT


def test_click_start_when_times_left(test_context: TestContext) -> None:
    """OCR 识别到正数(如 '3')→ 点击「按钮-开始」,命中按钮 → round_success(status='按钮-开始')。"""
    op = _setup_and_screenshot(test_context, '抽奖前')
    mock_map = {'3': MatchResultList()}
    with patch.object(test_context.ocr, 'crop_and_run_ocr', return_value=mock_map):
        result = op.click_start()
    assert result.is_success
    assert result.status == '按钮-开始'


def test_click_start_real_fixture(test_context: TestContext) -> None:
    """真实 fixture(抽奖前):剩余次数 >0 → 点击「按钮-开始」(端到端 GREEN)。"""
    op = _setup_and_screenshot(test_context, '抽奖前')
    result = op.click_start()
    # 抽奖前有剩余次数 → 走点击分支,命中「按钮-开始」模板
    assert result.is_success
    assert result.status == '按钮-开始'
