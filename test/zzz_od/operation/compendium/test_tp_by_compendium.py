import pytest
from test.conftest import TestContext

from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium


@pytest.mark.parametrize('mission_type_name', [None, ''])
def test_unspecified_mission_type_does_not_need_selection(
    test_context: TestContext,
    mission_type_name: str | None,
) -> None:
    """未指定副本名称时保持原有行为，停在分类页。"""
    op = TransportByCompendium(
        test_context, '训练', '区域巡防', mission_type_name
    )

    result = op.choose_mission_type()

    assert result.is_success
    assert result.status == '无需选择副本'


@pytest.mark.parametrize('mission_type_name', ['迅雷与裂爪', '不存在的副本'])
def test_unknown_mission_type_fails_instead_of_skipping(
    test_context: TestContext,
    mission_type_name: str,
) -> None:
    """明确指定但不存在的副本名称应失败，不能报传送成功。"""
    assert test_context.compendium_service.get_mission_type_data(
        '训练', '区域巡防', '迅脊与裂爪'
    ) is not None
    op = TransportByCompendium(
        test_context, '训练', '区域巡防', mission_type_name
    )

    result = op.choose_mission_type()

    assert result.is_fail
    assert result.status == f'非法的副本分类 {mission_type_name}'
