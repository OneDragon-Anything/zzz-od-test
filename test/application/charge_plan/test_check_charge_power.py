import test
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp


class TestCheckChargePower(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_check_charge_power(self):
        self.add_mock_screenshot('menu_charge_power')

        op = ChargePlanApp(self.ctx)
        op._init_before_execute()
        op.check_charge_power()
        self.assertEqual(266, op.charge_power)