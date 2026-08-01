"""CoffeeApp 对话点单测试(PR #2574 POINT_3 片刻闲)。

覆盖 ``dialog_choose_coffee`` 的选项态分支:
- 识别 ``对话框标题-汀曼大师`` + 在 ``右侧选项区域`` OCR 点击当天候选咖啡
- POINT_3(片刻闲)点单后返回 ``点单后跳过``;POINT_2(汀曼咖啡)返回 ``已点单``

fixture(`screens/咖啡店/对话点单-选项.webp`):POINT_3 片刻闲 未喝过选项态
(汀曼大师对话框 + 右侧「来杯「汀曼特调」/ 来杯『鲜萃红茶』/ 不喝了」)。
"""
from test.conftest import TestContext

from one_dragon.utils import os_utils
from zzz_od.application.coffee.coffee_app import CoffeeApp
from zzz_od.application.coffee.coffee_config import CoffeeTransportPoint


class TestCoffeeApp:
    """咖啡店 app 对话点单测试。"""

    def _make_op(self, test_context: TestContext) -> CoffeeApp:
        """mock 选项态截图 + 建 CoffeeApp。day_coffee 用 config 默认(汀曼特调)。"""
        test_context.mock_screen('咖啡店', '对话点单-选项')
        op = CoffeeApp(test_context)
        op.screenshot()
        return op

    def _expected_day_coffee(self, test_context: TestContext, op: CoffeeApp) -> str:
        """配置中当天的 day_coffee 名(默认汀曼特调),用于断言实际选中的咖啡。"""
        day = os_utils.get_current_day_of_week(test_context.game_account_config.game_refresh_hour_offset)
        return op.config.get_coffee_by_day(day)

    def test_dialog_choose_coffee_point3(self, test_context: TestContext) -> None:
        """POINT_3 选项态 → OCR 点候选咖啡 → 返回「点单后跳过」。"""
        op = self._make_op(test_context)
        op.config.transport_point = CoffeeTransportPoint.POINT_3.value.value
        result = op.dialog_choose_coffee()
        assert result.is_success, '选项态应识别候选咖啡并点击'
        assert result.status == '点单后跳过', f'POINT_3 点单后应返回「点单后跳过」,实际 {result.status}'
        assert op.chosen_coffee.coffee_name == self._expected_day_coffee(test_context, op), \
            f'应选择配置的 day_coffee({self._expected_day_coffee(test_context, op)}),实际 {op.chosen_coffee.coffee_name if op.chosen_coffee else None}'

    def test_dialog_choose_coffee_point2(self, test_context: TestContext) -> None:
        """POINT_2 选项态 → OCR 点候选咖啡 → 返回「已点单」(回归)。"""
        op = self._make_op(test_context)
        op.config.transport_point = CoffeeTransportPoint.POINT_2.value.value
        result = op.dialog_choose_coffee()
        assert result.is_success, '选项态应识别候选咖啡并点击'
        assert result.status == '已点单', f'POINT_2 点单后应返回「已点单」,实际 {result.status}'
        assert op.chosen_coffee.coffee_name == self._expected_day_coffee(test_context, op), \
            f'应选择配置的 day_coffee({self._expected_day_coffee(test_context, op)}),实际 {op.chosen_coffee.coffee_name if op.chosen_coffee else None}'
