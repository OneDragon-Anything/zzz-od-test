"""快捷手册“特训目标”动态副本选择测试。"""

from unittest.mock import patch

from test.conftest import TestContext

from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.operation.compendium.choose_training_goal import (
    ChooseTrainingGoal,
    build_training_goal_selection,
)
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge


def test_material_screenshot_uses_affordable_combat_simulation_cards(
    test_context: TestContext,
) -> None:
    """页面建议 20-100 电量、当前 95 时，应选 4 张卡消耗 80。"""
    screen = test_context.load_screen('快捷手册', '特训目标-材料')
    op = ChooseTrainingGoal(test_context, available_charge=95)

    selection = op.analyze_goal(screen)

    assert selection is not None
    assert selection.category_name == '实战模拟室'
    assert selection.card_num == '4'
    assert selection.required_charge == 80


def test_combat_simulation_explicitly_selects_five_cards_when_affordable() -> None:
    """电量足够时也显式选择 5 张，不能依赖游戏遗留的方案数量。"""
    selection = build_training_goal_selection(
        section_name='技能',
        charge_text='20-100',
        available_charge=102,
    )

    assert selection is not None
    assert selection.card_num == '5'
    assert selection.required_charge == 100


def test_drive_disc_screenshot_uses_first_recommendation(
    test_context: TestContext,
) -> None:
    """材料完成后页面顶部是驱动盘，应选择首条推荐并按 60 电量运行。"""
    screen = test_context.load_screen('快捷手册', '特训目标-驱动盘')
    op = ChooseTrainingGoal(test_context, available_charge=240)

    selection = op.analyze_goal(screen)

    assert selection is not None
    assert selection.category_name == '区域巡防'
    assert selection.required_charge == 60
    assert selection.go_point.y < 760


def test_missing_top_target_scrolls_down_to_find_drive_disc(
    test_context: TestContext,
) -> None:
    """材料完成项占据首屏时，等待一次后最多向下查找两次。"""
    op = ChooseTrainingGoal(test_context, available_charge=240)

    with (
        patch.object(op, 'analyze_goal', return_value=None),
        patch.object(op, '_after_round_wait'),
        patch.object(test_context.controller, 'drag_to') as drag_to,
    ):
        first = op.choose_goal()
        second = op.choose_goal()
        third = op.choose_goal()
        fourth = op.choose_goal()

    assert first.status == ChooseTrainingGoal.STATUS_NO_TARGET
    assert second.status == '向下查找推荐驱动盘'
    assert third.status == '向下查找推荐驱动盘'
    assert fourth.status == ChooseTrainingGoal.STATUS_NO_TARGET
    assert drag_to.call_count == 2


def test_expert_challenge_keeps_burnout_when_80_charge_is_available() -> None:
    """40-80 的专业挑战目标在电量够 80 时保留游戏预设的燃竭模式。"""
    selection = build_training_goal_selection(
        section_name='技能',
        charge_text='40-80',
        available_charge=97,
    )

    assert selection is not None
    assert selection.category_name == '专业挑战室'
    assert selection.required_charge == 80
    assert selection.use_burnout_mode is True


def test_expert_challenge_falls_back_to_normal_mode_with_40_charge() -> None:
    """只有 40-79 电量时关闭燃竭，先完成一次普通专业挑战。"""
    selection = build_training_goal_selection(
        section_name='技能',
        charge_text='40-80',
        available_charge=60,
    )

    assert selection is not None
    assert selection.category_name == '专业挑战室'
    assert selection.required_charge == 40
    assert selection.use_burnout_mode is False


def test_expert_challenge_keeps_enabled_burnout_mode(
    test_context: TestContext,
) -> None:
    """动态计划要求 80 电量时，不点击游戏内已经开启的燃竭开关。"""
    plan = ChargePlanItem(
        category_name='专业挑战室',
        mission_type_name='代理人方案培养',
        mission_name=None,
        use_burnout_mode=True,
    )
    op = ExpertChallenge(test_context, plan)

    result = op.close_burnout_mode()

    assert result.is_success
    assert result.status == '保留燃竭模式'


def test_non_drive_disc_60_charge_goal_is_notorious_hunt() -> None:
    """材料区固定 60 电量的目标属于恶名狩猎深度追猎。"""
    selection = build_training_goal_selection(
        section_name='核心技',
        charge_text='60',
        available_charge=240,
    )

    assert selection is not None
    assert selection.category_name == '恶名狩猎'
    assert selection.required_charge == 60


def test_dynamic_plan_inherits_source_settings_without_plan_count() -> None:
    """实际副本继承队伍、自动战斗和计划 ID，但每次只跑一轮后回页面重算。"""
    source = ChargePlanItem(
        category_name='特训目标',
        mission_type_name='',
        mission_name=None,
        auto_battle_config='测试指令',
        predefined_team_idx=2,
        notorious_hunt_buff_num=3,
        plan_id='source-id',
    )
    selection = build_training_goal_selection(
        section_name='驱动盘',
        charge_text='60',
        available_charge=240,
    )

    assert selection is not None
    child = selection.to_plan(source)
    assert child.category_name == '区域巡防'
    assert child.mission_type_name == '代理人方案培养'
    assert child.run_times == 0
    assert child.plan_times == 1
    assert child.plan_id == source.plan_id
    assert child.auto_battle_config == source.auto_battle_config
    assert child.predefined_team_idx == source.predefined_team_idx
    assert child.notorious_hunt_buff_num == source.notorious_hunt_buff_num
