from test.conftest import TestContext

from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.game_data.compendium import CompendiumService


def test_exchange_ether_battery_is_charge_plan_category() -> None:
    service = CompendiumService()
    service.reload()

    category_values = [
        item.value for item in service.get_charge_plan_category_list()
    ]

    assert '合成电池' in category_values
    category = service.get_category_data(
        '训练', '合成电池'
    )
    assert category is not None
    assert category.mission_type_list == []
    assert service.get_charge_plan_mission_type_list('合成电池') == []


def test_exchange_ether_battery_consumes_60_charge_power() -> None:
    plan = ChargePlanItem(
        category_name='合成电池',
        mission_type_name='',
        mission_name=None,
    )

    assert plan.estimated_charge_power == 60


def test_exchange_ether_battery_is_dispatched_in_transport(
    test_context: TestContext,
) -> None:
    app = ChargePlanApp(test_context)
    app.current_plan = ChargePlanItem(
        category_name='合成电池',
        mission_type_name='',
        mission_name=None,
    )

    result = app.transport()

    assert result.is_success
    assert result.status == '合成电池'
