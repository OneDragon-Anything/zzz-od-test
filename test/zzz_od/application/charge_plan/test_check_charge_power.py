from test.conftest import TestContext
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp


class TestCheckChargePower:

    def test_check_charge_power(self, test_context: TestContext):
        test_context.add_mock_screenshot_by_path('menu_charge_power.png')
        op = ChargePlanApp(test_context)
        op.screenshot()
        op.check_charge_power()
        assert 266 == op.charge_power
