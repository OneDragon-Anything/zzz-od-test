"""LostVoidApp.matrix_goto_entry 确认弹窗降级检测测试。

按 testing methodology 动作一:``matrix_goto_entry`` 正常走 ``round_by_goto_screen``
前往编队选择。点「下一步」后可能弹出确认弹窗(中途加入续传场景),导致画面识别不到
编队选择(``STATUS_SCREEN_UNKNOWN``)——此时降级检测一次确认按钮:
- 有确认(中途加入) → 点确认 → 直接进挚交会谈(大世界),跳过编队选择,
  ``next_region_type`` 置为 FRIENDLY_TALK。
- 有确认但点击失败 → 返回重试状态,继续重试。
- 无确认 / goto 正常成功 → 透传 goto 结果,不额外处理。

纯逻辑测试,不依赖画面 fixture:patch ``round_by_goto_screen`` 返回
``STATUS_SCREEN_UNKNOWN``(等不到编队画面),patch ``screen_utils.find_area`` 返回
确认按钮存在/不存在,patch ``round_by_find_and_click_area`` 返回固定成功/失败,断言分支结果。

源码行为(已读 ``lost_void_app.py`` 的 ``matrix_goto_entry`` 确认):
- ``round_by_goto_screen`` 结果 status 为 ``Operation.STATUS_SCREEN_UNKNOWN`` 时,
  才 ``screen_utils.find_area`` 查「迷失之地-矩阵行动 / 按钮-确认」:
  - ``TRUE`` → ``round_by_find_and_click_area`` 点确认:
    - 成功 → 返回 ``已进入挚交会谈``,``next_region_type`` 置 FRIENDLY_TALK。
    - 失败 → 返回 ``点击确认失败`` 重试。
  - 其它 → 透传原 goto 结果。
- 其它 status(成功 / 其它重试) → 直接透传,不查确认。
"""
from unittest.mock import patch

from test.conftest import TestContext

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from zzz_od.application.hollow_zero.lost_void.lost_void_app import LostVoidApp
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)


def _setup_op(test_context: TestContext) -> LostVoidApp:
    """构造 LostVoidApp 实例(直接实例化,无需 mock)。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    return LostVoidApp(
        test_context,
        lost_void_debug=False,
        next_region_type=LostVoidRegionType.ENTRY,
    )


def _success_result(status: str) -> OperationRoundResult:
    return OperationRoundResult(result=OperationRoundResultEnum.SUCCESS, status=status)


def _retry_result(status: str) -> OperationRoundResult:
    return OperationRoundResult(result=OperationRoundResultEnum.RETRY, status=status)


def test_screen_unknown_with_confirm_click_enter_friendly_talk(test_context: TestContext) -> None:
    """等不到编队画面 + 确认按钮存在 + 点击成功 → 返回「已进入挚交会谈」,next_region_type 置 FRIENDLY_TALK。"""
    op = _setup_op(test_context)
    with patch.object(LostVoidApp, 'round_by_goto_screen',
                      return_value=_retry_result(Operation.STATUS_SCREEN_UNKNOWN)), \
         patch('one_dragon.base.screen.screen_utils.find_area',
               return_value=FindAreaResultEnum.TRUE), \
         patch.object(LostVoidApp, 'round_by_find_and_click_area',
                      return_value=_success_result('按钮-确认')):
        result = op.matrix_goto_entry()
    assert result.is_success
    assert result.status == '已进入挚交会谈'
    assert op.next_region_type == LostVoidRegionType.FRIENDLY_TALK


def test_screen_unknown_with_confirm_click_fail_retry(test_context: TestContext) -> None:
    """等不到编队画面 + 确认按钮存在 + 点击失败 → 返回「点击确认失败」重试。"""
    op = _setup_op(test_context)
    with patch.object(LostVoidApp, 'round_by_goto_screen',
                      return_value=_retry_result(Operation.STATUS_SCREEN_UNKNOWN)), \
         patch('one_dragon.base.screen.screen_utils.find_area',
               return_value=FindAreaResultEnum.TRUE), \
         patch.object(LostVoidApp, 'round_by_find_and_click_area',
                      return_value=_retry_result('点击确认失败')):
        result = op.matrix_goto_entry()
    assert not result.is_success
    assert result.status == '点击确认失败'


def test_screen_unknown_without_confirm_passthrough(test_context: TestContext) -> None:
    """等不到编队画面 + 无确认按钮 → 透传原 goto 结果(不点确认,继续等编队画面)。"""
    op = _setup_op(test_context)
    with patch.object(LostVoidApp, 'round_by_goto_screen',
                      return_value=_retry_result(Operation.STATUS_SCREEN_UNKNOWN)), \
         patch('one_dragon.base.screen.screen_utils.find_area',
               return_value=FindAreaResultEnum.FALSE):
        result = op.matrix_goto_entry()
    assert not result.is_success
    assert result.status == Operation.STATUS_SCREEN_UNKNOWN


def test_goto_success_passthrough_without_confirm_check(test_context: TestContext) -> None:
    """正常到达编队选择 → 直接透传成功结果,不查确认按钮。"""
    op = _setup_op(test_context)
    with patch.object(LostVoidApp, 'round_by_goto_screen',
                      return_value=_success_result('迷失之地-矩阵行动-编队选择')) as mock_goto:
        result = op.matrix_goto_entry()
    assert result.is_success
    assert result.status == '迷失之地-矩阵行动-编队选择'
    mock_goto.assert_called_once()


def test_goto_other_retry_passthrough(test_context: TestContext) -> None:
    """goto 返回其它重试状态(如点击失败)→ 透传,不查确认。"""
    op = _setup_op(test_context)
    with patch.object(LostVoidApp, 'round_by_goto_screen',
                      return_value=_retry_result('按钮-前往挑战')):
        result = op.matrix_goto_entry()
    assert not result.is_success
    assert result.status == '按钮-前往挑战'
