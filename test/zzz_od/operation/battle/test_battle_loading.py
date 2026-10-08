"""用真实节点和框架执行循环验证机械硬盘加载等待，不启动游戏或模型。"""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from zzz_od.application.intel_board.intel_board_app import IntelBoardApp
from zzz_od.application.life_on_line.life_on_line_app import LifeOnLineApp
from zzz_od.application.shiyu_defense.shiyu_defense_battle import ShiyuDefenseBattle
from zzz_od.config.game_config import GameConfig
from zzz_od.hollow_zero.hollow_battle import HollowBattle
from zzz_od.operation.battle.base import BattleOpBase
from zzz_od.operation.battle.battle_loading import apply_battle_loading_wait
from zzz_od.operation.battle.lost_void import LostVoidBattleOp
from zzz_od.operation.compendium.area_patrol import AreaPatrol
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt


@dataclass
class Clock:
    """推进模拟时间，避免真的等待数分钟。"""

    now: float = 1000.0

    def time(self) -> float:
        """返回模拟时间。"""
        return self.now

    def sleep(self, seconds: float) -> None:
        """模拟原节点的轮询等待。"""
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """替换框架时钟和 sleep，执行循环本身仍使用真实实现。"""
    result = Clock()
    monkeypatch.setattr('time.time', result.time)
    monkeypatch.setattr('time.sleep', result.sleep)
    monkeypatch.setattr(
        'one_dragon.base.operation.operation.send_node_notify', lambda *args: None
    )
    return result


def make_context(hdd_mode: bool = False, timeout: int = 180) -> MagicMock:
    """使用真实配置属性，隔离游戏、通知和配置写盘。"""
    ctx = MagicMock()
    config = GameConfig.__new__(GameConfig)
    config.data = {'hdd_mode': hdd_mode, 'hdd_battle_loading_timeout': timeout}
    ctx.game_config = config
    ctx.debug_trace_bus = None
    ctx.run_context.is_context_stop = False
    ctx.run_context.is_context_pause = False
    ctx.run_context.is_context_running = True
    return ctx


class LoadingSequence(Operation):
    """原区域巡防加载节点加一个下游节点，验证失败不会误进战斗。"""

    def __init__(self, ctx: MagicMock, ready_after: float) -> None:
        """初始化模拟的加载画面时序。"""
        super().__init__(ctx, need_check_game_win=False)
        self.ready_after: float = ready_after
        self.entered_battle: bool = False

    def handle_init(self) -> None:
        """重复执行时清除下游状态。"""
        self.entered_battle = False

    @operation_node(
        name='等待战斗画面加载',
        is_start_node=True,
        node_max_retry_times=60,
        screenshot_before_round=False,
    )
    def wait_loading(self) -> OperationRoundResult:
        """调用真实的区域巡防等待节点。"""
        return AreaPatrol.wait_battle_screen(self)

    def round_by_find_area(
        self,
        screen: object,
        screen_name: str,
        area_name: str,
        retry_wait_round: float | None = None,
        retry_wait: float | None = None,
    ) -> OperationRoundResult:
        """只替换画面输入，沿用真实 round 方法及等待间隔。"""
        if self.operation_usage_time >= self.ready_after:
            return self.round_success(area_name)
        return self.round_retry(
            f'未找到 {area_name}', wait=retry_wait, wait_round_time=retry_wait_round
        )

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='开始战斗', screenshot_before_round=False)
    def enter_battle(self) -> OperationRoundResult:
        """记录是否执行了加载成功后的下游节点。"""
        self.entered_battle = True
        return self.round_success('进入战斗')


@pytest.mark.parametrize(
    'hdd_mode, ready_after, success',
    [
        (False, 52, True),
        (True, 52, True),
        (False, 65, False),
        (True, 65, True),
        (False, 111, False),
        (True, 111, True),
        (True, 181, False),
    ],
)
def test_same_loading_sequence(
    clock: Clock, hdd_mode: bool, ready_after: float, success: bool
) -> None:
    """同一时序对照：默认模式保留 60 次重试，机械盘有独立上限。"""
    op = LoadingSequence(make_context(hdd_mode), ready_after)
    result = op.execute()
    assert result.success is success
    assert op.entered_battle is success
    assert result.status == ('进入战斗' if success else '未找到 按键-普通攻击')
    if ready_after == 181:
        assert op.operation_usage_time == 180


def test_custom_timeout_and_repeat_run(clock: Clock) -> None:
    """自定义上限生效，同一操作重复运行重新计时。"""
    op = LoadingSequence(make_context(True, 90), 111)
    assert op.execute().success is False
    assert op.operation_usage_time == 90
    op.ready_after = 65
    assert op.execute().success is True
    assert op.operation_usage_time == 65


class HalfSecondSequence(LoadingSequence):
    """沿用真·拿命验收每轮半秒的加载节点。"""

    @operation_node(
        name='等待战斗画面加载',
        is_start_node=True,
        node_max_retry_times=60,
        screenshot_before_round=False,
    )
    def wait_loading(self) -> OperationRoundResult:
        """调用真实半秒轮询方法。"""
        return LifeOnLineApp.wait_battle_screen(self)


@pytest.mark.parametrize(
    'hdd_mode, success, elapsed', [(False, False, 30.5), (True, True, 65)]
)
def test_half_second_polling_keeps_interval(
    clock: Clock, hdd_mode: bool, success: bool, elapsed: float
) -> None:
    """默认的半秒轮询与重试额度保留，机械盘模式按秒而非次数计时。"""
    op = HalfSecondSequence(make_context(hdd_mode), 65)
    assert op.execute().success is success
    assert op.entered_battle is success
    assert op.operation_usage_time == elapsed
    assert op.chosen_team is True


def test_pause_does_not_consume_loading_budget(clock: Clock) -> None:
    """调用框架的暂停恢复方法，暂停的五分钟不扣加载额度。"""
    op = LoadingSequence(make_context(True), 65)
    op._init_before_execute()
    clock.sleep(50)
    op.ctx.run_context.is_context_running = False
    op._on_pause()
    clock.sleep(300)
    op.ctx.run_context.is_context_running = True
    op._on_resume()
    result = apply_battle_loading_wait(op, op.round_retry('未找到 按键-普通攻击'))
    assert result.result == OperationRoundResultEnum.WAIT
    assert op.operation_usage_time == 50
    assert clock.time() - op._current_node_start_time == 50


LOADING_CLASSES = [
    AreaPatrol,
    CombatSimulation,
    ExpertChallenge,
    NotoriousHunt,
    BattleOpBase,
    ShiyuDefenseBattle,
    HollowBattle,
    IntelBoardApp,
    LifeOnLineApp,
]


@pytest.mark.parametrize('cls', LOADING_CLASSES)
@pytest.mark.parametrize(
    'hdd_mode, elapsed, expected',
    [
        (False, 65, OperationRoundResultEnum.RETRY),
        (True, 65, OperationRoundResultEnum.WAIT),
        (True, 180, OperationRoundResultEnum.FAIL),
    ],
)
def test_each_loading_node(
    clock: Clock,
    cls: type[Operation],
    hdd_mode: bool,
    elapsed: float,
    expected: OperationRoundResultEnum,
) -> None:
    """逐个执行真实加载方法，保留识别目标、失败状态和共享节点声明。"""
    op = cls.__new__(cls)
    Operation.__init__(op, make_context(hdd_mode), need_check_game_win=False)
    op._current_node_start_time = clock.time() - elapsed
    original = OperationRoundResult(OperationRoundResultEnum.RETRY, '未找到加载画面')
    op.round_by_find_area = MagicMock(return_value=original)
    op._after_round_wait = MagicMock()
    shared_node = cls.wait_battle_screen.operation_node_annotation
    original_limit = shared_node.node_max_retry_times
    result = op.wait_battle_screen()
    assert result.result == expected
    assert result.status == '未找到加载画面'
    assert shared_node.node_max_retry_times == original_limit == 60
    assert all(
        call.args[1] == '战斗画面' for call in op.round_by_find_area.call_args_list
    )


@pytest.mark.parametrize('cls', LOADING_CLASSES)
def test_loaded_screen_continues_immediately(
    clock: Clock, cls: type[Operation]
) -> None:
    """已有战斗画面即成功，不强制等满上限；恶名狩猎的成功状态不变。"""
    op = cls.__new__(cls)
    Operation.__init__(op, make_context(True), need_check_game_win=False)
    op._current_node_start_time = clock.time()
    op.plan = SimpleNamespace(mission_type_name='恶名狩猎')
    op.round_by_find_area = MagicMock(
        return_value=OperationRoundResult(OperationRoundResultEnum.SUCCESS)
    )
    result = op.wait_battle_screen()
    assert result.is_success
    assert clock.time() == 1000
    if cls is NotoriousHunt:
        assert result.status == '恶名狩猎'


@pytest.mark.parametrize(
    'kind', [OperationRoundResultEnum.SUCCESS, OperationRoundResultEnum.FAIL]
)
def test_success_and_configuration_failure_are_passthrough(
    clock: Clock, kind: OperationRoundResultEnum
) -> None:
    """配置缺失失败不会被隐藏为等待，状态和 data 原样保留。"""
    op = LoadingSequence(make_context(True), 65)
    op._current_node_start_time = clock.time() - 180
    result = OperationRoundResult(
        kind,
        '区域未配置' if kind == OperationRoundResultEnum.FAIL else '已加载',
        object(),
    )
    assert apply_battle_loading_wait(op, result) is result


def test_no_shared_wait_state_between_instances(clock: Clock) -> None:
    """两个账号交替运行不串用模式或时间额度。"""
    hdd = LoadingSequence(make_context(True), 65)
    default = LoadingSequence(make_context(False), 65)
    assert hdd.execute().success is True
    assert default.execute().success is False
    assert hdd.execute().success is True
    assert (
        LoadingSequence.wait_loading.operation_node_annotation.node_max_retry_times
        == 60
    )


@pytest.mark.parametrize('cls', [BattleOpBase, IntelBoardApp, NotoriousHunt])
@pytest.mark.parametrize('hdd_mode', [False, True])
def test_interaction_fallback_still_succeeds(
    clock: Clock, cls: type[Operation], hdd_mode: bool
) -> None:
    """保留原来交互按钮可用时的成功分支，不延长已经成功的节点。"""
    op = cls.__new__(cls)
    Operation.__init__(op, make_context(hdd_mode), need_check_game_win=False)
    op._current_node_start_time = clock.time() - 65
    op._interact_as_wait_fallback = True
    op.plan = SimpleNamespace(mission_type_name='恶名狩猎')
    op.round_by_find_area = MagicMock(
        side_effect=[
            OperationRoundResult(
                OperationRoundResultEnum.RETRY, '未找到 按键-普通攻击'
            ),
            OperationRoundResult(OperationRoundResultEnum.SUCCESS, '按键-交互'),
        ]
    )
    assert op.wait_battle_screen().is_success
    assert clock.time() == 1000
    assert op.round_by_find_area.call_args.args[2] == '按键-交互'


def test_wait_and_timeout_keep_result_data(clock: Clock) -> None:
    """等待与失败都保留原识别状态及附加数据。"""
    op = LoadingSequence(make_context(True), 65)
    op._current_node_start_time = clock.time()
    data = object()
    original = OperationRoundResult(
        OperationRoundResultEnum.RETRY, '缺少战斗按钮', data
    )
    waiting = apply_battle_loading_wait(op, original)
    assert waiting.result == OperationRoundResultEnum.WAIT
    assert waiting.status == original.status and waiting.data is data
    clock.sleep(180)
    failed = apply_battle_loading_wait(op, original)
    assert failed.is_fail
    assert failed.status == original.status and failed.data is data


def test_new_node_gets_full_loading_budget(clock: Clock) -> None:
    """进入新节点时由真实框架重置时间，不沿用前一个节点的消耗。"""
    op = LoadingSequence(make_context(True), 65)
    op._current_node_start_time = clock.time() - 180
    original = op.round_retry('缺少战斗按钮')
    assert apply_battle_loading_wait(op, original).is_fail
    op._reset_status_for_new_node()
    assert (
        apply_battle_loading_wait(op, original).result == OperationRoundResultEnum.WAIT
    )


def test_lost_void_encounter_keeps_original_retry(clock: Clock) -> None:
    """同名迷失之地节点判断遭遇而非磁盘加载，不受机械盘模式影响。"""
    op = LostVoidBattleOp.__new__(LostVoidBattleOp)
    Operation.__init__(op, make_context(True), need_check_game_win=False)
    op._wait_battle = True
    op._current_node_start_time = clock.time() - 65
    op.ctx.lost_void.check_battle_encounter.return_value = False
    result = op.wait_battle_screen()
    assert result.result == OperationRoundResultEnum.RETRY
    assert result.status == '未进入战斗'


class OrdinarySequence(LoadingSequence):
    """同样声明 60 次重试，但不属于战斗加载的节点。"""

    @operation_node(
        name='等待战斗画面加载',
        is_start_node=True,
        node_max_retry_times=60,
        screenshot_before_round=False,
    )
    def wait_loading(self) -> OperationRoundResult:
        """模拟其他失败操作，完全沿用普通重试。"""
        return self.round_retry('普通节点', wait=1)


def test_ordinary_retry_limit_is_unchanged(clock: Clock) -> None:
    """其他节点即使也是 60 次，仍由原框架重试额度终止。"""
    op = OrdinarySequence(make_context(True), 65)
    result = op.execute()
    assert result.success is False
    assert result.status == '普通节点'
    assert op.entered_battle is False
    assert op.operation_usage_time == 61
    assert op.node_max_retry_times == 60
