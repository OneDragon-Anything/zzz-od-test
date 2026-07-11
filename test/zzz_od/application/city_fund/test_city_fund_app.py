"""CityFundApp 丽都城募测试。

覆盖:
- ``click_task_claim``:成长任务 tab 点「任务-全部领取」。

未覆盖(留标记):
- ``open_menu``(GotoMenu)/ ``click_fund``(菜单点丽都城募 tab):多画面导航。
- ``click_task``:依赖「开启丽都城募 / 按钮-确认 / 成长任务」多分支(条件态)。
- ``click_level`` / ``click_level_claim``:等级回馈 tab,等级-全部领取需等级达条件。
- ``back_to_world``:BackToNormalWorld。

fixture(`screens/丽都城募/`):`默认.webp`、`成长任务.webp`。
"""
from test.conftest import TestContext
from zzz_od.application.city_fund.city_fund_app import CityFundApp


class TestCityFundApp:
    """丽都城募 app 测试。"""

    def _make_op(self, test_context: TestContext, state: str) -> CityFundApp:
        test_context.mock_screen('丽都城募', state)
        op = CityFundApp(test_context)
        op.screenshot()
        return op

    def test_click_task_claim(self, test_context: TestContext) -> None:
        """成长任务 tab → 点「任务-全部领取」。"""
        op = self._make_op(test_context, '成长任务')
        result = op.click_task_claim()
        assert result.is_success, '应识别并点击「任务-全部领取」'
