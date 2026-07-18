from test.conftest import TestContext
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp


class TestCheckBatteryCharge:

    def test_check_battery_charge(self, test_context: TestContext):
        """#2348 后电量改从「快捷手册-资源栏」识别：电量 / 储蓄电量 / 以太电池。

        旧用例 test_check_charge_power 绑定的是已删除的菜单识别节点(check_charge_power / charge_power),
        此处改为按新流程 check_battery_charge 验证资源栏三项数字。
        """
        test_context.add_mock_screenshot_by_path('compendium_train_resource_bar.webp')
        op = ChargePlanApp(test_context)
        op.screenshot()
        op.check_battery_charge()
        assert 42 == op.battery_charge
        assert 67 == op.backup_battery_charge
        assert 27 == op.ether_battery
