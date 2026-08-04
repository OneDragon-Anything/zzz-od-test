"""实战模拟室结算材料识别与流程分支测试。"""

from unittest.mock import MagicMock

import numpy as np
import pytest
from cv2.typing import MatLike
from test.conftest import TestContext

from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
    ChargePlanRunModeEnum,
)
from zzz_od.operation.compendium import combat_simulation as combat_simulation_module
from zzz_od.operation.compendium.combat_simulation import CombatSimulation


def _material_plan(
    *,
    target: str = '特化以太芯片',
    goal: int = 10,
    counts: dict[str, int] | None = None,
) -> ChargePlanItem:
    """创建按以太芯片数量运行的计划。"""
    return ChargePlanItem(
        mission_type_name='代理人技能',
        mission_name='共鸣测试',
        run_mode=ChargePlanRunModeEnum.MATERIAL_COUNT.value.value,
        target_material_name=target,
        target_material_count=goal,
        material_counts=counts or {},
    )


def _match_list(*matches: MatchResult) -> MatchResultList:
    """创建保留所有位置的 OCR 匹配列表。"""
    result = MatchResultList(only_best=False)
    for match in matches:
        result.append(match, auto_merge=False)
    return result


def _reward_screen(
    rarity_items: list[tuple[str, int, int]],
) -> tuple[MatLike, dict[str, MatchResultList]]:
    """生成带奖励品质色带的结算页和对应 OCR 结果。"""
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    reward_left = 1280
    reward_top = 420
    color_map = {
        'A': (255, 0, 255),
        'B': (0, 0, 255),
        'C': (255, 255, 0),
        'unknown': (255, 255, 255),
    }
    ocr_map: dict[str, MatchResultList] = {}
    for rarity, quantity, x in rarity_items:
        match = MatchResult(1, x, 200, 20, 24)
        center_x = x + 10
        screen[
            reward_top + 179:reward_top + 197,
            reward_left + center_x - 25:reward_left + center_x + 25,
        ] = color_map[rarity]
        quantity_text = str(quantity)
        if quantity_text not in ocr_map:
            ocr_map[quantity_text] = _match_list(match)
        else:
            ocr_map[quantity_text].append(match, auto_merge=False)
    return screen, ocr_map


def test_read_material_reward_counts_aggregates_duplicate_rarities(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """五张卡的重复奖励按品质合并，双倍奖励也不会覆盖前一格。"""
    screen, ocr_map = _reward_screen([
        ('B', 4, 50),
        ('B', 2, 170),
        ('A', 1, 290),
        ('B', 16, 410),
        ('B', 12, 50),
        ('C', 5, 530),
    ])
    monkeypatch.setattr(test_context.ocr, 'run_ocr', lambda _part: ocr_map)
    op = CombatSimulation(test_context, _material_plan())

    counts = op.read_material_reward_counts(
        screen,
        ('特化以太芯片', '进阶以太芯片', '基础以太芯片'),
    )

    assert counts == {
        '特化以太芯片': 1,
        '进阶以太芯片': 34,
        '基础以太芯片': 5,
    }


def test_read_material_reward_counts_rejects_unknown_rarity(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """图标品质色无法判断时不写入可能错误的进度。"""
    screen, ocr_map = _reward_screen([('unknown', 3, 50)])
    monkeypatch.setattr(test_context.ocr, 'run_ocr', lambda _part: ocr_map)
    op = CombatSimulation(test_context, _material_plan())

    counts = op.read_material_reward_counts(
        screen,
        ('特化以太芯片', '进阶以太芯片', '基础以太芯片'),
    )

    assert counts is None


def test_read_material_reward_counts_from_live_snapshot(
    test_context: TestContext,
) -> None:
    """真实结算截图中的紫色与蓝色奖励分别计入对应材料。"""
    screen = test_context.load_screen('战斗画面', '实战模拟室-材料结算')
    op = CombatSimulation(test_context, _material_plan())

    counts = op.read_material_reward_counts(
        screen,
        ('特化以太芯片', '进阶以太芯片', '基础以太芯片'),
    )

    assert counts == {
        '特化以太芯片': 1,
        '进阶以太芯片': 2,
    }


def test_live_snapshot_reaches_intermediate_material_goal(
    test_context: TestContext,
) -> None:
    """真实结算截图写入进阶材料后，计划立即达到目标。"""
    plan = _material_plan(target='进阶以太芯片', goal=1)
    config = ChargePlanConfig.__new__(ChargePlanConfig)
    config.data = {}
    config.plan_list = [plan]
    config.save = MagicMock()
    op = CombatSimulation(test_context, plan)
    op.config = config
    op.last_screenshot = test_context.load_screen(
        '战斗画面',
        '实战模拟室-材料结算',
    )

    result = op.record_material_rewards()

    assert result.is_success
    assert plan.material_counts == {
        '特化以太芯片': 1,
        '进阶以太芯片': 2,
    }
    assert plan.current_material_count == 2
    assert plan.is_finished
    config.save.assert_called_once()


def test_single_material_reward_sums_all_slots(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """丁尼等单一材料无需判断品质，直接合并全部奖励格子。"""
    screen, ocr_map = _reward_screen([('unknown', 5000, 50), ('unknown', 5000, 170)])
    monkeypatch.setattr(test_context.ocr, 'run_ocr', lambda _part: ocr_map)
    op = CombatSimulation(test_context, _material_plan())

    counts = op.read_material_reward_counts(screen, ('丁尼',))

    assert counts == {'丁尼': 10000}


@pytest.mark.parametrize(
    ('plan', 'expected_try_next'),
    [
        (ChargePlanItem(run_times=0, plan_times=2), True),
        (ChargePlanItem(run_times=2, plan_times=2), False),
        (_material_plan(), True),
        (_material_plan(counts={'特化以太芯片': 10}), False),
    ],
)
def test_check_next_uses_updated_material_progress(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    plan: ChargePlanItem,
    expected_try_next: bool,
) -> None:
    """记录完奖励后，未达标继续挑战，达标才点击完成。"""
    captured: dict[str, bool] = {}

    class FakeChooseNext:
        def __init__(
            self,
            ctx: TestContext,
            try_next: bool,
            is_agent_plan: bool = False,
        ) -> None:
            captured['try_next'] = try_next

        def execute(self) -> OperationResult:
            return OperationResult(True, '战斗结果-完成')

    monkeypatch.setattr(
        combat_simulation_module,
        'ChooseNextOrFinishAfterBattle',
        FakeChooseNext,
    )
    op = CombatSimulation(test_context, plan)

    result = op.check_next()

    assert result.is_success
    assert captured['try_next'] is expected_try_next


def test_record_material_rewards_updates_config_once(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """结算页识别成功后一次写入本场全部材料。"""
    plan = _material_plan()
    op = CombatSimulation(test_context, plan)
    op.config = MagicMock()
    op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr(
        op,
        'read_material_reward_counts',
        lambda *args, **kwargs: {
            '特化以太芯片': 1,
            '进阶以太芯片': 12,
        },
    )

    result = op.record_material_rewards()

    assert result.is_success
    op.config.add_plan_material_counts.assert_called_once_with(
        plan,
        {'特化以太芯片': 1, '进阶以太芯片': 12},
    )


def test_record_material_rewards_retries_when_quantity_is_not_recognized(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """奖励数字无法识别时不写入零进度并明确重试。"""
    op = CombatSimulation(test_context, _material_plan())
    op.config = MagicMock()
    op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr(op, 'read_material_reward_counts', lambda *args, **kwargs: None)

    result = op.record_material_rewards()

    assert result.result == OperationRoundResultEnum.RETRY
    op.config.add_plan_material_counts.assert_not_called()


def test_reward_record_node_runs_before_next_choice(
    test_context: TestContext,
) -> None:
    """战斗结束后先记录材料，再根据更新后的进度选择按钮。"""
    op = CombatSimulation(test_context, _material_plan())
    op._init_network()

    battle_end_edges = op._node_edges_map['战斗结束']
    record_edges = op._node_edges_map['记录材料']

    assert any(edge.node_to.cn == '记录材料' for edge in battle_end_edges)
    assert any(edge.node_to.cn == '判断下一次' for edge in record_edges)
