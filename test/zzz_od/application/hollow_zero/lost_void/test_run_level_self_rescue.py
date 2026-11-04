"""LostVoidRunLevel 失败自救测试。

覆盖两类行为:
1. execute() 外层自救循环:失败 → 自救 → 重跑 / 自救失败返回 / restart_count 上限。
2. _try_rescue() 画面分发:已知交互画面复用对应操作、大世界直接脱困、未知画面走重开/退出兜底。

execute 循环测试用 monkeypatch 替换 Operation.execute(模拟框架执行结果),不依赖真实画面;
画面分发测试用 zzz-od-test/screens 存档截图驱动真实画面识别,子操作 execute 用 monkeypatch 模拟。
"""
import pytest
from test.conftest import TestContext

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_bangboo_store import (
    LostVoidBangbooStore,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import (
    LostVoidChooseCommon,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_gear import (
    LostVoidChooseGear,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_lottery import (
    LostVoidLottery,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_route_change import (
    LostVoidRouteChange,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle
from zzz_od.operation.challenge_mission.restart_in_battle import RestartInBattle


def _setup_op(test_context: TestContext) -> LostVoidRunLevel:
    """构造一个 ENTRY 类型的 LostVoidRunLevel 实例,前置加载武备/挑战配置。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    return LostVoidRunLevel(test_context, LostVoidRegionType.ENTRY)


# ========== execute() 自救循环 ==========

def test_execute_rescue_then_success(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """失败 1 次 → 自救成功 → 重跑成功:返回成功, restart_count 累加为 1。"""
    op = _setup_op(test_context)
    calls = {'n': 0}

    def fake_execute(self: LostVoidRunLevel) -> OperationResult:
        calls['n'] += 1
        if calls['n'] == 1:
            return OperationResult(False, '等待画面返回')
        return OperationResult(True, '成功')

    monkeypatch.setattr(Operation, 'execute', fake_execute)
    monkeypatch.setattr(LostVoidRunLevel, '_try_rescue', lambda self: True)

    result = op.execute()

    assert result.success
    assert result.status == '成功'
    assert op.restart_count == 1
    assert calls['n'] == 2, '失败后自救成功应重跑一次'


def test_execute_rescue_fail_returns_fail(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """自救失败 → 尝试退出挑战后返回失败, restart_count 累加为 1。"""
    op = _setup_op(test_context)
    monkeypatch.setattr(Operation, 'execute', lambda self: OperationResult(False, '卡死'))
    monkeypatch.setattr(LostVoidRunLevel, '_try_rescue', lambda self: False)
    exited = {'called': False}
    monkeypatch.setattr(LostVoidRunLevel, '_exit_lost_void_gracefully', lambda self: exited.update(called=True))

    result = op.execute()

    assert not result.success
    assert result.status == '卡死'
    assert op.restart_count == 1
    assert exited['called'], '自救失败后应尝试退出挑战回入口'


def test_execute_no_rescue_when_limit_reached(test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """restart_count 已达上限 3 → 失败直接返回,不再尝试自救,但尝试退出挑战。"""
    op = _setup_op(test_context)
    op.restart_count = 3
    monkeypatch.setattr(Operation, 'execute', lambda self: OperationResult(False, '卡死'))
    exited = {'called': False}
    monkeypatch.setattr(LostVoidRunLevel, '_exit_lost_void_gracefully', lambda self: exited.update(called=True))

    result = op.execute()

    assert not result.success
    assert op.restart_count == 3, '达到上限后不应再累加自救次数'
    assert exited['called'], '自救次数耗尽后应尝试退出挑战回入口'


# ========== _try_rescue() 画面分发 ==========

@pytest.mark.parametrize('screen_name,state,op_cls', [
    ('迷失之地-通用选择', '选1枚鸣徽', LostVoidChooseCommon),
    ('迷失之地-武备选择', '初始战术棱镜方案', LostVoidChooseGear),
    ('迷失之地-邦布商店', '商店', LostVoidBangbooStore),
    ('迷失之地-路径迭换', '选定位卡', LostVoidRouteChange),
    ('迷失之地-抽奖机', '抽奖前', LostVoidLottery),
], ids=['choose_common', 'choose_gear', 'bangboo_store', 'route_change', 'lottery'])
def test_try_rescue_known_interact_screens(test_context: TestContext,
                                           monkeypatch: pytest.MonkeyPatch,
                                           screen_name: str,
                                           state: str,
                                           op_cls: type) -> None:
    """已知交互画面 → 复用对应操作处理 → 自救成功。"""
    test_context.mock_screen(screen_name, state)
    op = _setup_op(test_context)
    monkeypatch.setattr(op_cls, 'execute', lambda self: OperationResult(True, '处理完成'))

    assert op._try_rescue() is True


def test_try_rescue_normal_world(test_context: TestContext) -> None:
    """大世界 → 已恢复可寻路状态 → 自救成功。"""
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op = _setup_op(test_context)

    assert op._try_rescue() is True


def test_try_rescue_unknown_screen_restart_fail(test_context: TestContext,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """未知画面 → 战斗内重开失败 → 退出挑战失败 → 自救失败。"""
    import numpy as np
    test_context.add_mock_screenshot(np.zeros((1080, 1920, 3), dtype=np.uint8))
    op = _setup_op(test_context)
    monkeypatch.setattr(op.ctx.auto_battle_context, 'stop_auto_battle', lambda: None)
    monkeypatch.setattr(RestartInBattle, 'execute', lambda self: OperationResult(False, '未找到退出战斗'))
    monkeypatch.setattr(ExitInBattle, 'execute', lambda self: OperationResult(False, '未找到退出战斗'))

    assert op._try_rescue() is False


def test_try_rescue_unknown_screen_restart_success(test_context: TestContext,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """未知画面 → 战斗内重开成功 → 自救成功。"""
    import numpy as np
    test_context.add_mock_screenshot(np.zeros((1080, 1920, 3), dtype=np.uint8))
    op = _setup_op(test_context)
    monkeypatch.setattr(RestartInBattle, 'execute', lambda self: OperationResult(True, '重新开始'))

    assert op._try_rescue() is True
