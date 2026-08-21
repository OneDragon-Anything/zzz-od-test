from types import SimpleNamespace

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
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
    app._previous_round_result = OperationRoundResult(
        OperationRoundResultEnum.FAIL,
        status=charge_plan_const.STATUS_SWITCH_TEAM,
        data='战斗失败',
    )
    return app


@pytest.mark.parametrize(('old_idx', 'expected_idx'), [(-1, 0), (0, 1)])
def test_switches_to_next_team_and_saves(old_idx: int, expected_idx: int) -> None:
    plan = ChargePlanItem(predefined_team_idx=old_idx)
    config = _FakeConfig()
    app = _new_app(plan, config)

    result = app.switch_team()

    assert result.is_success
    assert result.status == ChargePlanApp.STATUS_RETRY_CURRENT_PLAN
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

    result = app.switch_team()

    assert result.status == ChargePlanApp.STATUS_RETRY_CURRENT_PLAN
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

    exhausted = app.switch_team()
    assert exhausted.status == ChargePlanApp.STATUS_TEAM_EXHAUSTED

    app._previous_round_result = exhausted
    result = app.skip_plan_or_finish()

    assert result.status == expected_status
    assert plan.skipped is expected_skipped


def test_switch_team_status_routes_are_declared() -> None:
    switch_edges = ChargePlanApp.switch_team.operation_edge_annotation
    switch_sources = {
        edge.node_from_name
        for edge in switch_edges
        if not edge.success and edge.status == charge_plan_const.STATUS_SWITCH_TEAM
    }
    retry_edges = ChargePlanApp.back_before_open_compendium.operation_edge_annotation
    exhausted_edges = ChargePlanApp.skip_plan_or_finish.operation_edge_annotation

    assert switch_sources == {'实战模拟室', '区域巡防', '专业挑战室', '恶名狩猎'}
    assert any(
        edge.node_from_name == '切换配队'
        and edge.status == ChargePlanApp.STATUS_RETRY_CURRENT_PLAN
        for edge in retry_edges
    )
    assert any(
        edge.node_from_name == '切换配队'
        and edge.status == ChargePlanApp.STATUS_TEAM_EXHAUSTED
        for edge in exhausted_edges
    )


def test_last_team_ends_agent_plan_when_skip_is_disabled() -> None:
    plan = ChargePlanItem(
        mission_type_name='代理人方案培养',
        predefined_team_idx=2,
    )
    config = _FakeConfig()
    app = _new_app(plan, config, team_count=3)

    exhausted = app.switch_team()
    app._previous_round_result = exhausted
    result = app.skip_plan_or_finish()

    assert result.status == ChargePlanApp.STATUS_ROUND_FINISHED
    assert plan.skipped is False
