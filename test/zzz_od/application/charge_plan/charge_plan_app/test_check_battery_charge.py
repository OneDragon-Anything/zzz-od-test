import pytest
from test.conftest import TestContext

from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp


class TestCheckBatteryCharge:

    @pytest.mark.parametrize(
        ('image_name', 'expected'),
        [
            # 快捷手册资源栏字段向右对齐，某项数字位数越多，该项及其左侧字段会整体向左移动
            # 从左到右：电量固定为3位数，储蓄电量上限为4位数（2400），以太电池上限为3位数（400）
            # 理论上的 343（即储蓄电量和以太电池的位数最多时）可确定储蓄电量字段的左边界
            # 理论上的 311（即储蓄电量和以太电池的位数最少时）可确定储蓄电量字段的右边界
            # 其余位数组合均落在两者之间，因为三个数字的活动范围固定，字段间隔充足
            # 以太电池为1位时，电量数字最靠右，但仍位于储蓄电量左边界左侧
            # 以太电池为3位时，以太电池数字最靠左，但仍位于储蓄电量右边界右侧

            # ('sample_343_01.webp', (240, 2400, 263)), ('sample_343_02.webp', (341, 2399, 115)),
            # ('sample_311.webp', (129, 0, 2)),

            # 其他截图（不需要全部有），目标是通过大量样例检验准确率绝对为100%
            ('sample_343_01.webp', (240, 2400, 263)), ('sample_343_02.webp', (341, 2399, 115)),
            # TODO: sample_342.webp
            # TODO: sample_341.webp
            ('sample_333_01.webp', (215, 443, 150)), ('sample_333_02.webp', (15, 388, 155)),
            ('sample_332_01.webp', (132, 273, 49)), ('sample_332_02.webp', (61, 100, 52)), ('sample_332_03.webp', (6, 273, 50)),
            # TODO: sample_331.webp
            # TODO: sample_323.webp
            ('sample_322_01.webp', (181, 99, 50)), ('sample_322_02.webp', (62, 99, 52)), ('sample_322_03.webp', (3, 38, 54)),
            ('sample_321.webp', (193, 48, 4)),
            # TODO: sample_313.webp
            ('sample_312_01.webp', (103, 0, 53)), ('sample_312_02.webp', (38, 4, 54)), ('sample_312_03.webp', (3, 0, 54)),
            ('sample_311.webp', (129, 0, 2)),
            # 粗体字
            ('sample_bold_343_01.webp', (240, 2400, 263)), ('sample_bold_343_02.webp', (341, 2399, 115)),
            ('sample_bold_332.webp', (400, 419, 82)),
        ],
    )
    def test_check_battery_charge(
        self,
        test_context: TestContext,
        image_name: str,
        expected: tuple[int, int, int],
    ):
        test_context.add_mock_screenshot_by_path(image_name)
        op = ChargePlanApp(test_context)
        op.screenshot()
        result = op.check_battery_charge()
        assert result.is_success
        assert expected == (
            op.battery_charge,
            op.backup_battery_charge,
            op.ether_battery,
        )
