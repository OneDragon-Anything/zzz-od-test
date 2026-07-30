"""按键可用-普通攻击 状态写入测试。

验证 check_battle_state 在普攻按钮可用(in_battle=True)时写入该状态,
按钮缺失(in_battle=False)时清除状态(is_clear=True)。

check_battle_state 内部会往线程池提交 dodge/agent/target/quick/switch_backup/chain
等子任务,它们依赖完整 ctx 与模型;本测试 patch 掉这些子任务,聚焦"状态是否写入"
这一同步行为(is_normal_attack_btn_available 也 patch 以控制 in_battle)。
"""
from unittest.mock import MagicMock, patch

import numpy as np

from zzz_od.auto_battle.auto_battle_context import AutoBattleContext
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum


def _make_ctx() -> MagicMock:
    """mock ctx(AutoBattleContext.__init__ 只读取属性,MagicMock 足够)。"""
    ctx = MagicMock()
    ctx.project_config.screen_standard_width = 1920
    return ctx


def _make_auto_battle_context() -> AutoBattleContext:
    abc = AutoBattleContext(_make_ctx())
    # 屏蔽提交到线程池的子任务(依赖完整 ctx/模型),使测试聚焦状态写入
    abc.dodge_context = MagicMock()
    abc.agent_context = MagicMock()
    abc.target_context = MagicMock()
    return abc


def _patch_sub_checks(abc: AutoBattleContext):
    """patch 掉 check_battle_state 直接调用的本类方法(check_quick_assist 等)。"""
    return [
        patch.object(abc, 'check_quick_assist'),
        patch.object(abc, 'check_switch_backup'),
        patch.object(abc, 'check_chain_attack'),
    ]


def test_normal_attack_ready_state_recorded_when_in_battle() -> None:
    """in_battle=True → 写入 按键可用-普通攻击,last_record_time == screenshot_time。"""
    abc = _make_auto_battle_context()
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    patches = _patch_sub_checks(abc)
    for p in patches:
        p.start()
    try:
        with patch.object(abc, 'is_normal_attack_btn_available', return_value=True):
            abc.check_battle_state(screen, screenshot_time=100.0)
    finally:
        for p in patches:
            p.stop()

    recorder = abc.state_record_service.get_state_recorder(
        BattleStateEnum.STATUS_NORMAL_ATTACK_READY.value)
    assert recorder is not None
    assert recorder.last_record_time == 100.0


def test_normal_attack_ready_state_cleared_when_button_missing() -> None:
    """in_battle=False 清除状态:True@100 后 False@200,last_record_time 被清成 0。"""
    abc = _make_auto_battle_context()
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    patches = _patch_sub_checks(abc)
    for p in patches:
        p.start()
    try:
        with patch.object(abc, 'is_normal_attack_btn_available', side_effect=[True, False]):
            abc.check_battle_state(screen, screenshot_time=100.0)
            abc.check_battle_state(screen, screenshot_time=200.0)
    finally:
        for p in patches:
            p.stop()

    recorder = abc.state_record_service.get_state_recorder(
        BattleStateEnum.STATUS_NORMAL_ATTACK_READY.value)
    assert recorder is not None
    assert recorder.last_record_time == 0  # False@200 is_clear 清成 0
