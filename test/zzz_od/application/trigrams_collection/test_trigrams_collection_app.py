"""TrigramsCollectionApp 卦象集录测试。

覆盖:
- ``get_trigram``(主界面):OCR「卦象集录」→ 点「区域-获取卦象」(round_wait, status=卦象集录)。
- ``get_trigram``(今日已领取):OCR「确认」→ 标 claim_reward + click(round_wait, status=确认)。

未覆盖(留标记,见 `卦象集录.md` 备注):
- ``transport`` / ``move_and_interact``:run_operation Transport + controller interact(朝向 + 时机,手动难复现)。
- 滑动获取卦象子态(当日已领取看不到):OCR「滑动屏幕以获取卦象」→ drag_to 来回拖。
- ``back_at_last``:BackToNormalWorld。

fixture(`screens/卦象集录/`):`主界面.webp`、`今日已领取.webp`。

注:`get_trigram` 返回 ``round_wait``(点 area / click 后等下一轮),非 ``round_success``,
故断言用 ``status``(匹配到的目标词)而非 ``is_success``。
"""
from test.conftest import TestContext
from zzz_od.application.trigrams_collection.trigrams_collection_app import TrigramsCollectionApp


class TestTrigramsCollectionApp:
    """卦象集录 app 测试。"""

    def _make_op(self, test_context: TestContext, state: str) -> TrigramsCollectionApp:
        test_context.mock_screen('卦象集录', state)
        op = TrigramsCollectionApp(test_context)
        op.screenshot()
        return op

    def test_get_trigram_main(self, test_context: TestContext) -> None:
        """主界面 → OCR「卦象集录」→ 点区域-获取卦象(round_wait, status=卦象集录)。"""
        op = self._make_op(test_context, '主界面')
        result = op.get_trigram()
        assert result.status == '卦象集录', '应识别「卦象集录」并点区域-获取卦象'

    def test_get_trigram_claimed(self, test_context: TestContext) -> None:
        """今日已领取 → OCR「确认」→ 标 claim_reward + click(round_wait, status=确认)。"""
        op = self._make_op(test_context, '今日已领取')
        result = op.get_trigram()
        assert result.status == '确认', '应识别「确认」并点'
        assert op.claim_reward is True, '应标记已获取卦象'
