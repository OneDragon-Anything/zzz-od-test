"""迷失之地「确定」按钮场景识别测试。

修复背景(commit 956f742b):通用选择 `按钮-确定` 原 rect 过宽([466,758,1406,977],940px)
+ lcs_percent=0.5,引发两个故障:
- ppocrv6:`crop_first=True` 对该宽 text rect 检不出「确定」→ 通用选择无法精准匹配 → 整局卡死。
- ppocrv5:宽 rect + lcs 0.5 把大世界场景文字「以太稳定」(LCS=0.5)误配成「确定」+ TAB 在场
  → 大世界被误判成通用选择 → LostVoidChooseCommon 标题为空 → 死循环。
修复:rect 收紧到 [855,795,1165,975] + lcs_percent 提到 0.7。

本测试用中央存档 fixture(`zzz-od-test/screens/迷失之地-*/`)覆盖:
- 通用选择真帧 → 正确识别为通用选择。
- **回归**:大世界+「以太稳定」帧(原误判场景)→ 识别为大世界,不误判为通用选择。
- 挑战结果 确定态/完成态 → 按钮-确定/完成 可检出。
"""
from test.conftest import TestContext

from one_dragon.base.screen import screen_utils


class TestLostVoidQuedingButton:

    def test_choose_common_match(self, test_context: TestContext):
        """通用选择真帧:精准识别为「迷失之地-通用选择」(按钮-确定 + TAB 双 id_mark 命中)。"""
        img = test_context.load_screen('迷失之地-通用选择', '选1张卡牌')
        assert screen_utils.get_match_screen_name(test_context, img) == '迷失之地-通用选择'

    def test_normal_world_not_false_matched_as_choose_common(self, test_context: TestContext):
        """回归:大世界+「以太稳定」帧(原 ppocrv5 误判卡死场景)→ 识别为大世界,不误判为通用选择。

        修复前:宽 按钮-确定 rect + lcs 0.5 把「以太稳定」误配成「确定」+ TAB → 误判通用选择 → 死循环。
        """
        img = test_context.load_screen('迷失之地-大世界', '玛琳前-以太稳定')
        result = screen_utils.get_match_screen_name(test_context, img)
        assert result == '迷失之地-大世界', f'应识别为大世界,却被识别为 {result}(通用选择误判回归失败)'

    def test_choose_common_queding_area(self, test_context: TestContext):
        """通用选择 `按钮-确定` 区(收紧后的 rect):真帧上能检出「确定」。"""
        img = test_context.load_screen('迷失之地-通用选择', '选1张卡牌')
        area = test_context.screen_loader.get_area('迷失之地-通用选择', '按钮-确定')
        assert screen_utils.find_by_ocr(test_context, img, '确定', area=area, crop_first=True)

    def test_battle_result_queding_area(self, test_context: TestContext):
        """挑战结果-确定态:`按钮-确定` 可检出。"""
        img = test_context.load_screen('迷失之地-挑战结果', '确定态')
        area = test_context.screen_loader.get_area('迷失之地-挑战结果', '按钮-确定')
        assert screen_utils.find_by_ocr(test_context, img, '确定', area=area, crop_first=True)

    def test_battle_result_wancheng_area(self, test_context: TestContext):
        """挑战结果-完成态:`按钮-完成` 可检出。"""
        img = test_context.load_screen('迷失之地-挑战结果', '完成态')
        area = test_context.screen_loader.get_area('迷失之地-挑战结果', '按钮-完成')
        assert screen_utils.find_by_ocr(test_context, img, '完成', area=area, crop_first=True)
