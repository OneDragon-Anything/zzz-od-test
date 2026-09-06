"""验证换队的真实配置保存和双倍临时计划生命周期。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from one_dragon.utils import os_utils
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ChargePlanConfig:
    """隔离所有配置路径，仍使用真实 YAML 保存与读取。"""
    monkeypatch.setattr(
        os_utils, 'get_path_under_work_dir',
        lambda *parts: str(tmp_path.joinpath(*parts)),
    )
    result = ChargePlanConfig(99, 'one_dragon')
    result.plan_list = [ChargePlanItem(predefined_team_idx=-1, run_times=2, plan_times=4)]
    result.save()
    return result


def new_app(config: ChargePlanConfig, temporary: bool) -> ChargePlanApp:
    """只初始化本组测试使用的应用状态，不启动游戏服务。"""
    app = object.__new__(ChargePlanApp)
    app.config = config
    app.ctx = SimpleNamespace(team_config=SimpleNamespace(team_list=[
        SimpleNamespace(name=f'编队{i + 1}') for i in range(3)
    ]))
    app.temp_plan = config.combat_simulation_double_reward_config if temporary else None
    app.current_plan = app.temp_plan if temporary else config.plan_list[0]
    app.last_tried_plan = None
    app._previous_node = None
    app._previous_round_result = None
    return app


@pytest.mark.parametrize('temporary', [False, True])
def test_sequential_switch_survives_reload_without_persisting_runtime_fields(
    config: ChargePlanConfig, temporary: bool,
) -> None:
    """连续换队只改变来源配置的队伍，耗尽后不回绕也不再写盘。"""
    config.combat_simulation_double_reward_config = ChargePlanItem(
        predefined_team_idx=-1, plan_times=4, battle_timeout_seconds=120,
    )
    before_regular = config.plan_list[0].to_dict()
    before_double = config.combat_simulation_double_reward_config.to_dict()
    app = new_app(config, temporary)
    if temporary:
        app.current_plan.card_num = '5'
        app.current_plan.run_times = 1
        app.current_plan.plan_times = 1

    for team_idx in range(3):
        app.current_plan.skipped = True
        assert app.switch_team('战斗失败')
        reloaded = ChargePlanConfig(99, 'one_dragon')
        expected_regular = dict(before_regular)
        expected_double = dict(before_double)
        (expected_double if temporary else expected_regular)['predefined_team_idx'] = team_idx
        assert reloaded.plan_list[0].to_dict() == expected_regular
        assert reloaded.combat_simulation_double_reward_config.to_dict() == expected_double
        assert app.current_plan.skipped is False
        assert app.last_tried_plan is None

    saved = Path(config.file_path).read_bytes()
    assert app.switch_team('战斗超时') is False
    assert app.current_plan.predefined_team_idx == 2
    assert Path(config.file_path).read_bytes() == saved
    assert app.current_plan.run_times == (1 if temporary else 2)
    assert len(config.plan_list) == 1


@pytest.mark.parametrize('skip', [False, True])
def test_exhausted_double_plan_is_cleared(
    config: ChargePlanConfig, skip: bool,
) -> None:
    """双倍计划耗尽后清理临时项，允许跳过时继续首条正式计划。"""
    config.skip_plan = skip
    app = new_app(config, True)
    app.current_plan.predefined_team_idx = 2
    assert app.switch_team('战斗失败') is False
    app._previous_round_result = OperationRoundResult(
        OperationRoundResultEnum.FAIL, status=ChargePlanApp.STATUS_TEAM_EXHAUSTED,
    )
    result = app.skip_plan_or_finish()
    assert app.temp_plan is None
    assert result.status == (
        ChargePlanApp.STATUS_FIND_NEXT_PLAN if skip else ChargePlanApp.STATUS_ROUND_FINISHED
    )
    if skip:
        assert app.find_next_plan().is_success
        assert app.current_plan is config.plan_list[0]
        assert app.current_plan.skipped is False
    else:
        assert app.last_tried_plan is None


@pytest.mark.parametrize('success', [False, True])
def test_double_plan_completion_clears_temporary_plan(
    config: ChargePlanConfig, success: bool,
) -> None:
    """双倍子操作成功或普通失败后均恢复正式计划调度。"""
    app = new_app(config, True)
    app._previous_round_result = OperationRoundResult(
        OperationRoundResultEnum.SUCCESS if success else OperationRoundResultEnum.FAIL,
    )
    assert app.challenge_complete().is_success
    assert app.temp_plan is None
    assert app.find_next_plan().is_success
    assert app.current_plan is config.plan_list[0]
    assert config.plan_list[0].run_times == 2
