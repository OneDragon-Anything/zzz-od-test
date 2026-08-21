import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.operation.compendium import combat_simulation as combat_simulation_module
from zzz_od.operation.compendium.area_patrol import AreaPatrol
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt

COMBAT_OPERATION_TYPES = (CombatSimulation, AreaPatrol, ExpertChallenge, NotoriousHunt)


def _new_combat_operation(
    operation_type: type,
    timeout_seconds: int,
    elapsed_seconds: float,
    in_battle: bool,
    last_result: str | None = None,
) -> object:
    operation = object.__new__(operation_type)
    auto_battle_context = SimpleNamespace(
        last_check_end_result=last_result,
        check_battle_state=Mock(return_value=in_battle),
        stop_auto_battle=Mock(),
    )
    operation.ctx = SimpleNamespace(
        auto_battle_context=auto_battle_context,
        battle_assistant_config=SimpleNamespace(screenshot_interval=0),
    )
    operation.plan = ChargePlanItem(battle_timeout_seconds=timeout_seconds)
    operation._switch_team_requested = False
    operation._current_node_start_time = time.time() - elapsed_seconds
    operation.last_screenshot = None
    operation.last_screenshot_time = time.time()
    if operation_type is NotoriousHunt:
        operation.use_charge_power = True
    return operation


@pytest.mark.parametrize('operation_type', COMBAT_OPERATION_TYPES)
def test_timeout_disabled_keeps_battling(operation_type: type) -> None:
    operation = _new_combat_operation(operation_type, 0, 100, True)

    result = operation.auto_battle()

    assert result.result == OperationRoundResultEnum.WAIT
    assert operation._switch_team_requested is False


@pytest.mark.parametrize('operation_type', COMBAT_OPERATION_TYPES)
def test_before_threshold_keeps_battling(operation_type: type) -> None:
    operation = _new_combat_operation(operation_type, 60, 50, True)

    result = operation.auto_battle()

    assert result.result == OperationRoundResultEnum.WAIT
    assert operation._switch_team_requested is False


@pytest.mark.parametrize('operation_type', COMBAT_OPERATION_TYPES)
def test_threshold_requests_exit_only_while_in_battle(operation_type: type) -> None:
    operation = _new_combat_operation(operation_type, 60, 61, True)

    result = operation.auto_battle()

    assert result.is_fail
    assert result.status == Operation.STATUS_TIMEOUT
    assert operation._switch_team_requested is True
    operation.ctx.auto_battle_context.stop_auto_battle.assert_called_once()


@pytest.mark.parametrize('operation_type', COMBAT_OPERATION_TYPES)
def test_settlement_screen_is_not_treated_as_timeout(operation_type: type) -> None:
    operation = _new_combat_operation(operation_type, 60, 61, False)

    result = operation.auto_battle()

    assert result.result == OperationRoundResultEnum.WAIT
    assert operation._switch_team_requested is False


@pytest.mark.parametrize('operation_type', COMBAT_OPERATION_TYPES)
def test_existing_600_second_timeout_keeps_original_status(operation_type: type) -> None:
    operation = _new_combat_operation(operation_type, 0, 601, True)

    result = operation.auto_battle()

    assert result.is_fail
    assert result.status == Operation.STATUS_TIMEOUT
    assert operation._switch_team_requested is False


@pytest.mark.parametrize('operation_type', (CombatSimulation, AreaPatrol, ExpertChallenge))
def test_regular_battle_failure_requests_team_switch(
    monkeypatch: pytest.MonkeyPatch,
    operation_type: type,
) -> None:
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda seconds: None)
    operation = _new_combat_operation(operation_type, 60, 10, False)
    operation.round_by_find_and_click_area = Mock(
        return_value=OperationRoundResult(
            OperationRoundResultEnum.SUCCESS,
            status='战斗结果-撤退',
        )
    )

    result = operation.battle_fail()

    assert result.is_fail
    assert result.status == charge_plan_const.STATUS_SWITCH_TEAM
    assert result.data == '战斗失败'


@pytest.mark.parametrize('operation_type', (CombatSimulation, AreaPatrol, ExpertChallenge))
def test_regular_battle_failure_keeps_old_behavior_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    operation_type: type,
) -> None:
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda seconds: None)
    operation = _new_combat_operation(operation_type, 0, 10, False)
    operation.round_by_find_and_click_area = Mock(
        return_value=OperationRoundResult(
            OperationRoundResultEnum.SUCCESS,
            status='战斗结果-撤退',
        )
    )

    result = operation.battle_fail()

    assert result.is_success
    assert result.status == '战斗结果-撤退'


def test_notorious_hunt_enabled_skips_rewind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda seconds: None)
    operation = _new_combat_operation(NotoriousHunt, 60, 10, False)
    operation.round_by_find_and_click_area = Mock(
        return_value=OperationRoundResult(
            OperationRoundResultEnum.SUCCESS,
            status='战斗结果-撤退',
        )
    )

    retreat_result = operation.battle_fail()
    first_area_name = operation.round_by_find_and_click_area.call_args.args[2]
    exit_result = operation.battle_fail_exit()

    assert retreat_result.is_success
    assert first_area_name == '战斗结果-撤退'
    assert exit_result.is_fail
    assert exit_result.status == charge_plan_const.STATUS_SWITCH_TEAM


def test_notorious_hunt_disabled_keeps_rewind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda seconds: None)
    operation = _new_combat_operation(NotoriousHunt, 0, 10, False)
    operation.round_by_find_and_click_area = Mock(
        return_value=OperationRoundResult(
            OperationRoundResultEnum.SUCCESS,
            status='战斗结果-倒带',
        )
    )

    result = operation.battle_fail()

    first_area_name = operation.round_by_find_and_click_area.call_args.args[2]
    assert result.is_success
    assert first_area_name == '战斗结果-倒带'


@pytest.mark.parametrize(
    ('operation_type', 'original_status'),
    [
        (AreaPatrol, AreaPatrol.STATUS_FIGHT_TIMEOUT),
        (ExpertChallenge, ExpertChallenge.STATUS_FIGHT_TIMEOUT),
        (NotoriousHunt, NotoriousHunt.STATUS_FIGHT_TIMEOUT),
    ],
)
@pytest.mark.parametrize('switch_requested', [False, True])
def test_result_exit_preserves_hard_timeout_or_requests_switch(
    operation_type: type,
    original_status: str,
    switch_requested: bool,
) -> None:
    operation = _new_combat_operation(operation_type, 60, 61, False)
    operation._switch_team_requested = switch_requested
    operation.round_by_find_and_click_area = Mock(
        return_value=OperationRoundResult(OperationRoundResultEnum.SUCCESS)
    )

    result = operation.click_result_exit()

    expected_status = charge_plan_const.STATUS_SWITCH_TEAM if switch_requested else original_status
    assert result.is_fail
    assert result.status == expected_status


@pytest.mark.parametrize('switch_requested', [False, True])
def test_combat_simulation_exit_preserves_hard_timeout_or_requests_switch(
    monkeypatch: pytest.MonkeyPatch,
    switch_requested: bool,
) -> None:
    class _ExitInBattle:

        def __init__(self, ctx: object, screen_name: str, area_name: str) -> None:
            return None

        def execute(self) -> object:
            return object()

    monkeypatch.setattr(combat_simulation_module, 'ExitInBattle', _ExitInBattle)
    operation = _new_combat_operation(CombatSimulation, 60, 61, False)
    operation._switch_team_requested = switch_requested
    operation.round_by_op_result = Mock(
        return_value=OperationRoundResult(OperationRoundResultEnum.SUCCESS)
    )

    result = operation.battle_timeout()

    expected_status = (
        charge_plan_const.STATUS_SWITCH_TEAM
        if switch_requested
        else CombatSimulation.STATUS_FIGHT_TIMEOUT
    )
    assert result.is_fail
    assert result.status == expected_status
