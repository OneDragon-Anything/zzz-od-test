"""EngagementRewardApp 活跃度奖励测试。

覆盖:
- ``goto_compendium_daily``:已到快捷手册-日常 → 识别成功。

未覆盖(留标记,见 `快捷手册-日常.md` 备注):
- ``click_reward`` / ``check_reward`` / ``check_engagement``:依赖活跃度领取状态
  (本次活跃度已满,无可领),且涉及领取确认/奖励预览弹窗,待活跃度可领时补。
- ``back_at_first`` / ``back_afterwards``:``BackToNormalWorld`` 通用导航(且从拆解
  画面回大世界有卡点,见 doc 备注)。

fixture(`screens/快捷手册-日常/`):`默认.webp`。
"""
from test.conftest import TestContext
from zzz_od.application.engagement_reward.engagement_reward_app import EngagementRewardApp


class TestEngagementRewardApp:
    """活跃度奖励 app 测试。"""

    def test_goto_compendium_daily(self, test_context: TestContext) -> None:
        """已到快捷手册-日常 → goto_compendium_daily 识别成功。"""
        test_context.mock_screen('快捷手册-日常', '默认')
        op = EngagementRewardApp(test_context)
        op.screenshot()
        result = op.goto_compendium_daily()
        assert result.is_success, '应识别到快捷手册-日常'
