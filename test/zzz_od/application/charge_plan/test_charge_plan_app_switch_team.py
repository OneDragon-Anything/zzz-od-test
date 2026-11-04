from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from zzz_od.application.charge_plan import charge_plan_app as charge_plan_app_module
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem


class _FakeConfig:

    def __init__(self, double_reward_plan: ChargePlanItem | None = None) -> None:
        self.save_count: int = 0
        self.skip_plan: bool = False
        self._double_reward_plan: ChargePlanItem = double_reward_plan or ChargePlanItem()

    def save(self) -> None:
        self.save_count += 1

    @property
    def combat_simulation_double_reward_config(self) -> ChargePlanItem:
        return ChargePlanItem.from_dict(self._double_reward_plan.to_dict())

    @combat_simulation_double_reward_config.setter
    def combat_simulation_double_reward_config(self, value: ChargePlanItem) -> None:
        self._double_reward_plan = ChargePlanItem.from_dict(value.to_dict())


def _new_app(
    plan: ChargePlanItem,
    config: _FakeConfig,
    team_count: int = 3,
    temp_plan: ChargePlanItem | None = None,
) -> ChargePlanApp:
    app = object.__new__(ChargePlanApp)
    team_list = [SimpleNamespace(idx=i, name=f'编队{i + 1}') for i in range(team_count)]
    app.ctx = SimpleNamespace(team_config=SimpleNamespace(team_list=team_list))
    app.config = config
    app.current_plan = plan
    app.temp_plan = temp_plan
    app.last_tried_plan = plan
    app._previous_node = None
    app._previous_round_result = None
    return app


@pytest.mark.parametrize(('old_idx', 'expected_idx'), [(-1, 0), (0, 1)])
def test_switches_to_next_team_and_saves(old_idx: int, expected_idx: int) -> None:
    plan = ChargePlanItem(predefined_team_idx=old_idx)
    config = _FakeConfig()
    app = _new_app(plan, config)

    switched = app.switch_team('战斗失败')

    assert switched is True
    assert plan.predefined_team_idx == expected_idx
    assert config.save_count == 1
    assert app.last_tried_plan is None


def test_double_reward_switch_only_persists_team() -> None:
    saved_plan = ChargePlanItem(
        predefined_team_idx=-1,
        run_times=0,
        plan_times=4,
        card_num='默认数量',
    )
    temp_plan = ChargePlanItem(
        predefined_team_idx=-1,
        run_times=1,
        plan_times=1,
        card_num='5',
    )
    config = _FakeConfig(saved_plan)
    app = _new_app(temp_plan, config, temp_plan=temp_plan)

    switched = app.switch_team('战斗失败')

    assert switched is True
    assert temp_plan.predefined_team_idx == 0
    assert config._double_reward_plan.predefined_team_idx == 0
    assert config._double_reward_plan.run_times == 0
    assert config._double_reward_plan.plan_times == 4
    assert config._double_reward_plan.card_num == '默认数量'
    assert config.save_count == 0


@pytest.mark.parametrize(
    ('skip_plan', 'expected_status', 'expected_skipped'),
    [
        (True, ChargePlanApp.STATUS_FIND_NEXT_PLAN, True),
        (False, ChargePlanApp.STATUS_ROUND_FINISHED, False),
    ],
)
def test_last_team_obeys_skip_plan(
    skip_plan: bool,
    expected_status: str,
    expected_skipped: bool,
) -> None:
    plan = ChargePlanItem(predefined_team_idx=2)
    config = _FakeConfig()
    config.skip_plan = skip_plan
    app = _new_app(plan, config, team_count=3)

    switched = app.switch_team('战斗超时')
    assert switched is False

    app._previous_round_result = OperationRoundResult(
        OperationRoundResultEnum.FAIL,
        status=charge_plan_const.STATUS_TEAM_EXHAUSTED,
    )
    result = app.skip_plan_or_finish()

    assert result.status == expected_status
    assert plan.skipped is expected_skipped


def test_team_exhausted_routes_are_declared_without_full_retry_route() -> None:
    retry_edges = ChargePlanApp.back_before_open_compendium.operation_edge_annotation
    exhausted_edges = ChargePlanApp.skip_plan_or_finish.operation_edge_annotation
    exhausted_sources = {
        edge.node_from_name
        for edge in exhausted_edges
        if not edge.success and edge.status == charge_plan_const.STATUS_TEAM_EXHAUSTED
    }

    assert exhausted_sources == {'实战模拟室', '区域巡防', '专业挑战室', '恶名狩猎'}
    assert all(edge.node_from_name != '切换配队' for edge in retry_edges)


@pytest.mark.parametrize(
    ('method_name', 'operation_name'),
    [
        ('combat_simulation', 'CombatSimulation'),
        ('area_patrol', 'AreaPatrol'),
        ('expert_challenge', 'ExpertChallenge'),
        ('notorious_hunt', 'NotoriousHunt'),
    ],
)
def test_charge_plan_passes_switch_callback_to_suboperation(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    operation_name: str,
) -> None:
    captured: dict[str, object] = {}

    class _FakeOperation:

        def __init__(
            self,
            ctx: object,
            plan: ChargePlanItem,
            use_charge_power: bool = False,
            switch_team_callback: object | None = None,
        ) -> None:
            captured['ctx'] = ctx
            captured['plan'] = plan
            captured['use_charge_power'] = use_charge_power
            captured['switch_team_callback'] = switch_team_callback

        def execute(self) -> object:
            return object()

    monkeypatch.setattr(charge_plan_app_module, operation_name, _FakeOperation)
    app = object.__new__(ChargePlanApp)
    app.ctx = object()
    app.current_plan = ChargePlanItem()
    app.round_by_op_result = Mock(return_value='done')

    result = getattr(app, method_name)()

    assert result == 'done'
    assert captured['ctx'] is app.ctx
    assert captured['plan'] is app.current_plan
    callback = captured['switch_team_callback']
    assert callback.__self__ is app
    assert callback.__func__ is ChargePlanApp.switch_team
    if method_name == 'notorious_hunt':
        assert captured['use_charge_power'] is True


def test_last_team_ends_agent_plan_when_skip_is_disabled() -> None:
    plan = ChargePlanItem(
        mission_type_name='代理人方案培养',
        predefined_team_idx=2,
    )
    config = _FakeConfig()
    app = _new_app(plan, config, team_count=3)

    switched = app.switch_team('战斗失败')
    assert switched is False
    app._previous_round_result = OperationRoundResult(
        OperationRoundResultEnum.FAIL,
        status=charge_plan_const.STATUS_TEAM_EXHAUSTED,
    )
    result = app.skip_plan_or_finish()

    assert result.status == ChargePlanApp.STATUS_ROUND_FINISHED
    assert plan.skipped is False
