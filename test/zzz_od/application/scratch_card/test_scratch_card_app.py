"""ScratchCardApp 刮刮卡测试。

覆盖:
- ``scratch``:刮态 → 找到「每日可刮取一次」→ drag 刮层(success)。

未覆盖(留标记,见 `报刊亭.md` 备注):
- ``transport`` / ``wait_world``:run_operation Transport + 加载等待。
- ``move_and_interact``:controller ``move_w``+``interact``(朝向 + 时机,手动难复现,
  需 transport 重置朝向 + move 后 sleep + F 长按 0.2)。
- ``click_scratch_card``:嗷呜对话多分支(叫醒他 / 嗷呜 / 刮刮卡),依赖子态。
- ``back_to_world``:BackToNormalWorld。

fixture(`screens/报刊亭/`):`默认.webp`(报刊亭场景)、`刮态.webp`。
"""
from test.conftest import TestContext
from zzz_od.application.scratch_card.scratch_card_app import ScratchCardApp


class TestScratchCardApp:
    """刮刮卡 app 测试。"""

    def _make_op(self, test_context: TestContext, state: str) -> ScratchCardApp:
        test_context.mock_screen('报刊亭', state)
        op = ScratchCardApp(test_context)
        op.screenshot()
        return op

    def test_scratch(self, test_context: TestContext) -> None:
        """刮态 → 找到「每日可刮取一次」→ drag 刮层(应 success)。"""
        op = self._make_op(test_context, '刮态')
        result = op.scratch()
        assert result.is_success, '应识别「每日可刮取一次」并 drag 刮层'
