"""验证真实节点图的退出、等待、换队和再次出战。

使用 FixtureController 推进多帧和记录真实区域坐标点击；视觉识别返回剧本中的
区域集合，选队子操作替换为有入口断言的假操作。这里验证流程契约，不验证 OCR
精度；完整游戏截图识别和实际选队仍需实机验收。
"""

import importlib
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
)
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_loader import ScreenContext
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, OcrClickResultEnum
from one_dragon.utils import os_utils
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.config.team_config import TeamConfig
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle
from zzz_od.operation.compendium.area_patrol import AreaPatrol
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt

OPERATION_TYPES = (CombatSimulation, AreaPatrol, ExpertChallenge, NotoriousHunt)


class _PhaseController(FixtureController):
    """用帧编号关联区域识别结果，仍通过区域点击推进 FixtureController。"""

    @property
    def current_frame(self) -> np.ndarray:
        """返回只携带剧本帧编号的测试输入，不伪装为真实截图。"""
        return np.full((1, 1, 3), self.phase_idx, dtype=np.uint8)


class _BattleSegment:
    """从战斗节点开始，执行到再次出战或失败结束。"""

    visited: list[str]

    def handle_init(self) -> None:
        """限定被测区间，不改变其中的业务节点和分支。"""
        self.visited = []
        self._current_node = self._node_map['自动战斗']
        self._current_node_start_time = time.time() - 602
        self._node_edges_map['出战'] = []

    def _execute_one_round(self) -> OperationRoundResult:
        """记录真实流转；WAIT 轮次由测试看门狗限制。"""
        self.visited.append(self._current_node.cn)
        return super()._execute_one_round()


class _WatchedExit(WatchdogOperationMixin, ExitInBattle):
    """给退出子操作的 WAIT 循环也设置看门狗。"""


@pytest.mark.parametrize('operation_type', OPERATION_TYPES)
@pytest.mark.parametrize('trigger', ['timeout', 'failure'])
@pytest.mark.parametrize('exhausted', [False, True])
def test_exit_then_retry_or_exhaust(
    operation_type: type[Operation], trigger: str, exhausted: bool,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """四类副本经真实 execute 退出；有下一队才选队并出战。"""
    screens = ScreenContext()
    screens.reload(from_separated_files=True)
    monkeypatch.setattr(os_utils, 'get_path_under_work_dir', lambda *parts: str(tmp_path.joinpath(*parts)))
    monkeypatch.setattr('one_dragon.base.operation.operation.time.sleep', lambda seconds: None)
    monkeypatch.setattr('one_dragon.base.operation.operation.send_node_notify', Mock())

    ctx = SimpleNamespace(game_config=SimpleNamespace(), screen_loader=screens)
    ctx.run_context = ApplicationRunContext(ctx)
    ctx.unlisten_all_event = ctx.run_context.event_bus.unlisten_all_event
    ctx.controller = _PhaseController(ctx)
    ctx.controller.mouse_move = Mock()
    ctx.battle_assistant_config = SimpleNamespace(screenshot_interval=0)
    ctx.team_config = TeamConfig(99)
    ctx.team_config.update('team_list', [
        {'name': '队伍1', 'agent_id_list': ['anby']},
        {'name': '队伍2', 'agent_id_list': ['ellen']},
    ])
    assert len(ctx.team_config.team_list) == 20
    ctx.auto_battle_context = SimpleNamespace(
        last_check_end_result='普通战斗-撤退' if trigger == 'failure' else None,
        check_battle_state=Mock(return_value=True), stop_auto_battle=Mock(),
    )

    config = ChargePlanConfig(99, 'one_dragon')
    plan = ChargePlanItem(predefined_team_idx=1 if exhausted else 0, battle_timeout_seconds=600, card_num='5')
    config.plan_list = [plan]
    config.save()
    app = object.__new__(ChargePlanApp)
    app.ctx, app.config = ctx, config
    app.current_plan, app.temp_plan, app.last_tried_plan = plan, None, plan

    phases: list[dict] = []
    visible: list[set[tuple[str, str]]] = []

    def add_phase(areas: set[tuple[str, str]], click: tuple[str, str] | None = None) -> None:
        """阶段只接受目标区域点击，防止其它恢复点击错误推进。"""
        visible.append(areas)
        phase = {'frame': ('mock', str(len(phases)))}
        if click is not None:
            phase['exit'] = ('on_click_in', *click)
        phases.append(phase)

    if trigger == 'timeout':
        add_phase(set(), ('战斗画面', '菜单'))
        add_phase({('战斗-菜单', '按钮-退出战斗')}, ('战斗-菜单', '按钮-退出战斗'))
        add_phase({('战斗-菜单', '按钮-退出战斗-确认')}, ('战斗-菜单', '按钮-退出战斗-确认'))
        if operation_type is not CombatSimulation:
            add_phase({('战斗-挑战结果-失败', '按钮-退出')}, ('战斗-挑战结果-失败', '按钮-退出'))
    else:
        add_phase({('战斗画面', '战斗结果-撤退')}, ('战斗画面', '战斗结果-撤退'))
        if operation_type is NotoriousHunt:
            add_phase({('战斗画面', '战斗结果-退出')}, ('战斗画面', '战斗结果-退出'))

    prepare_phase = len(phases)
    add_phase({('实战模拟室', '下一步'), ('画面-通用', '左上角-区域')}, ('实战模拟室', '下一步'))
    add_phase({('实战模拟室', '出战')}, ('实战模拟室', '出战'))
    add_phase(set())
    ctx.controller.set_phases(phases)

    def find_area(ctx: object, screen: np.ndarray, screen_name: str, area_name: str,
                  **kwargs: object) -> FindAreaResultEnum:
        """仅替换视觉结果，保留真实区域定义和操作 helper 的 WAIT/RETRY。"""
        if screens.get_area(screen_name, area_name) is None:
            return FindAreaResultEnum.AREA_NO_CONFIG
        found = (screen_name, area_name) in visible[int(screen[0, 0, 0])]
        return FindAreaResultEnum.TRUE if found else FindAreaResultEnum.FALSE

    def find_and_click(ctx: object, screen: np.ndarray, screen_name: str, area_name: str,
                       **kwargs: object) -> OcrClickResultEnum:
        """识别命中后点击当前 screen_info 区域，由控制器决定是否推进。"""
        if find_area(ctx, screen, screen_name, area_name) != FindAreaResultEnum.TRUE:
            return OcrClickResultEnum.OCR_CLICK_NOT_FOUND
        ctx.controller.click(screens.get_area(screen_name, area_name).center)
        return OcrClickResultEnum.OCR_CLICK_SUCCESS

    monkeypatch.setattr(screen_utils, 'find_area', find_area)
    monkeypatch.setattr(screen_utils, 'find_and_click_area', find_and_click)

    exits: list[_WatchedExit] = []

    def new_exit(ctx: object, screen_name: str, area_name: str) -> _WatchedExit:
        """执行真实退出子操作，避免构造 OpenGame。"""
        op = object.__new__(_WatchedExit)
        Operation.__init__(op, ctx, need_check_game_win=False)
        op.wait_screen_name, op.wait_area_name = screen_name, area_name
        op.watchdog_max_rounds = 30
        exits.append(op)
        return op

    chosen: list[int] = []

    class ChooseTeam:
        """断言只有在出战准备页才进入选队，选队失败不能被忽略。"""

        def __init__(self, ctx: object, team_indices: list[int]) -> None:
            self.team_indices: list[int] = team_indices

        def execute(self) -> OperationResult:
            """记录收到的真实当前计划队伍。"""
            assert ctx.controller.phase_idx == prepare_phase + 1
            chosen.extend(self.team_indices)
            return OperationResult(True)

    class Deploy:
        """只替换出战子操作的视觉内部，验证出战点击顺序。"""

        def __init__(self, ctx: object) -> None:
            self.ctx: object = ctx

        def execute(self) -> OperationResult:
            """选择队伍后才能点击出战。"""
            assert chosen == [1]
            ctx.controller.click(screens.get_area('实战模拟室', '出战').center)
            return OperationResult(True)

    module = importlib.import_module(operation_type.__module__)
    monkeypatch.setattr(module, 'ExitInBattle', new_exit)
    monkeypatch.setattr(module, 'ChoosePredefinedTeam', ChooseTeam)
    if operation_type is not NotoriousHunt:
        monkeypatch.setattr(module, 'Deploy', Deploy)
    watched_type = type('WatchedBattle', (_BattleSegment, WatchdogOperationMixin, operation_type), {})
    op = object.__new__(watched_type)
    Operation.__init__(op, ctx, need_check_game_win=False)
    op.plan, op.switch_team_callback = plan, app.switch_team
    op._switch_team_requested = False
    op.use_charge_power = True
    op.watchdog_max_rounds = 40

    enter_running_state(ctx)
    try:
        result = op.execute()
    finally:
        reset_running_state(ctx, op)
        for exit_op in exits:
            reset_running_state(ctx, exit_op)
        ctx.run_context._executor.shutdown(wait=True)

    assert '切换配队' in op.visited
    assert plan.card_num == '5' and plan.run_times == 0
    if exhausted:
        assert not result.success
        assert result.status == ChargePlanApp.STATUS_TEAM_EXHAUSTED
        assert chosen == []
        assert ctx.controller.phase_idx == prepare_phase
    else:
        assert result.success
        assert chosen == [1]
        assert op.visited.count('下一步') >= 2  # 点击后 WAIT，再识别出战页。
        assert ctx.controller.phase_idx == len(phases) - 1
        assert ChargePlanConfig(99, 'one_dragon').plan_list[0].predefined_team_idx == 1
