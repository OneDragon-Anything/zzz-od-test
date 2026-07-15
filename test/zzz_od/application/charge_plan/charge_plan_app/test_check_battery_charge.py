import pytest
from test.conftest import TestContext

from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp


class TestCheckBatteryCharge:

    @pytest.mark.parametrize(
        ('image_name', 'expected'),
        [
            ('sample_333.webp', (215, 443, 150)),
            ('sample_233.webp', (15, 388, 155)),
            # TODO: sample_133.webp
            # TODO: sample_323.webp
            # TODO: sample_223.webp
            # TODO: sample_123.webp
            # TODO: sample_313.webp
            # TODO: sample_213.webp
            # TODO: sample_113.webp
            ('sample_332.webp', (132, 273, 49)),
            ('sample_232.webp', (61, 100, 52)),
            ('sample_132.webp', (6, 273, 50)),
            ('sample_322.webp', (181, 99, 50)),
            ('sample_222.webp', (62, 99, 52)),
            ('sample_122.webp', (3, 38, 54)),
            ('sample_312.webp', (103, 0, 53)),
            ('sample_212.webp', (38, 4, 54)),
            ('sample_112.webp', (3, 0, 54)),
            # TODO: sample_331.webp
            # TODO: sample_231.webp
            # TODO: sample_131.webp
            ('sample_321.webp', (193, 48, 4)),
            # TODO: sample_221.webp
            # TODO: sample_121.webp
            ('sample_311.webp', (129, 0, 2)),
            # TODO: sample_211.webp
            # TODO: sample_111.webp
            ('sample_bold.webp', (400, 419, 82)),
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
