"""体力计划按材料数量运行的配置测试。"""

from unittest.mock import MagicMock

import pytest
from test.conftest import TestContext

import zzz_od.application.charge_plan.charge_plan_config as charge_plan_config_module
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
    ChargePlanRunModeEnum,
)


def _make_config(plans: list[ChargePlanItem]) -> ChargePlanConfig:
    """创建不读写配置文件的体力计划配置。"""
    config = ChargePlanConfig.__new__(ChargePlanConfig)
    config.data = {}
    config.plan_list = plans
    config.save = MagicMock()
    return config


def _material_plan(
    *,
    target: str = '特化以太芯片',
    goal: int = 10,
    counts: dict[str, int] | None = None,
    include_synthesis: bool = False,
) -> ChargePlanItem:
    """创建按材料数量运行的实战模拟室计划。"""
    return ChargePlanItem(
        mission_type_name='代理人技能',
        mission_name='共鸣测试',
        run_mode=ChargePlanRunModeEnum.MATERIAL_COUNT.value.value,
        target_material_name=target,
        target_material_count=goal,
        material_counts=counts or {},
        include_synthesis=include_synthesis,
    )


def test_legacy_plan_defaults_to_run_times_mode() -> None:
    """旧配置没有新字段时，仍按计划次数判断完成。"""
    plan = ChargePlanItem.from_dict({'run_times': 1, 'plan_times': 2})

    assert plan.run_mode == ChargePlanRunModeEnum.RUN_TIMES.value.value
    assert plan.is_finished is False


@pytest.mark.parametrize(
    ('target', 'expected'),
    [
        ('特化以太芯片', ('特化以太芯片', '进阶以太芯片', '基础以太芯片')),
        ('进阶以太芯片', ('进阶以太芯片', '基础以太芯片')),
        ('特化型强攻组件', ('特化型强攻组件', '增强型强攻组件', '强攻组件')),
        ('增强型强攻组件', ('增强型强攻组件', '强攻组件')),
        ('先行者认证章', ('先行者认证章', '高阶强攻认证章', '初阶强攻认证章')),
        ('统御者认证章', ('统御者认证章', '高阶支援认证章', '初阶支援认证章')),
        ('高阶强攻认证章', ('高阶强攻认证章', '初阶强攻认证章')),
        ('资深调查员记录', ('资深调查员记录', '正式调查员记录', '见习调查员记录')),
        ('正式调查员记录', ('正式调查员记录', '见习调查员记录')),
        ('黄金汽水瓶盖', ('黄金汽水瓶盖',)),
    ],
)
def test_material_tier_names(target: str, expected: tuple[str, ...]) -> None:
    """常见芯片、组件和认证章能找到同系列低级材料。"""
    plan = _material_plan(target=target)

    assert plan.material_tier_names == expected


def test_current_material_count_can_include_synthesis() -> None:
    """低级材料按 3:1 逐级合成，并与已有中级材料共同折算。"""
    plan = _material_plan(
        goal=12,
        counts={
            '特化以太芯片': 10,
            '进阶以太芯片': 2,
            '基础以太芯片': 3,
        },
        include_synthesis=True,
    )

    assert plan.current_material_count == 11
    assert plan.is_finished is False

    plan.material_counts['基础以太芯片'] += 9

    assert plan.current_material_count == 12
    assert plan.is_finished is True


def test_current_material_count_ignores_lower_tiers_when_disabled() -> None:
    """关闭合成折算时只计算目标材料本身。"""
    plan = _material_plan(
        goal=11,
        counts={'特化以太芯片': 10, '进阶以太芯片': 30},
        include_synthesis=False,
    )

    assert plan.current_material_count == 10
    assert plan.is_finished is False


def test_base_material_does_not_apply_synthesis_ratio() -> None:
    """经验材料没有合成功能，即使旧配置残留开关也只计算目标材料。"""
    plan = ChargePlanItem(
        mission_type_name='基础材料',
        mission_name='调查专项',
        run_mode=ChargePlanRunModeEnum.MATERIAL_COUNT.value.value,
        target_material_name='资深调查员记录',
        target_material_count=10,
        material_counts={'资深调查员记录': 2, '正式调查员记录': 30},
        include_synthesis=True,
    )

    assert plan.current_material_count == 2


def test_custom_template_does_not_support_material_count() -> None:
    """自定义模板会混合材料系列，不能只按品质判断目标材料。"""
    plan = ChargePlanItem(
        mission_type_name='自定义模板',
        mission_name='自定义卡组1',
    )

    assert plan.supports_material_count is False


def test_material_plan_without_valid_target_is_safely_finished() -> None:
    """材料名为空或目标数为零时不消耗体力。"""
    assert _material_plan(target='', goal=10).is_finished is True
    assert _material_plan(target='特化以太芯片', goal=0).is_finished is True


@pytest.mark.parametrize(
    ('plan', 'reason'),
    [
        (
            ChargePlanItem(
                mission_type_name='自定义模板',
                mission_name='自定义卡组1',
                run_mode=ChargePlanRunModeEnum.MATERIAL_COUNT.value.value,
                target_material_name='特化以太芯片',
                target_material_count=10,
            ),
            '当前副本不支持按材料数量运行',
        ),
        (_material_plan(target='', goal=10), '目标材料为空'),
        (_material_plan(target='特化以太芯片', goal=0), '目标材料数必须大于 0'),
    ],
)
def test_invalid_material_plan_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    plan: ChargePlanItem,
    reason: str,
) -> None:
    """配置文件中的非法材料计划会安全停止并留下可定位日志。"""
    warning = MagicMock()
    monkeypatch.setattr(charge_plan_config_module.log, 'warning', warning)

    assert plan.is_finished is True
    warning.assert_called_once()
    assert f'reason={reason}' in warning.call_args.args[0]


def test_validate_material_target_against_selected_mission(
    test_context: TestContext,
) -> None:
    """目标材料必须属于所选副本，防止按同品质的其他材料误计数。"""
    valid = _material_plan(target='特化以太芯片')
    invalid = _material_plan(target='特化物理芯片')

    assert ChargePlanConfig.validate_item(test_context, valid) is None
    error = ChargePlanConfig.validate_item(test_context, invalid)
    assert error is not None
    assert 'target_material_name' in error


def test_config_selects_by_material_progress() -> None:
    """候选计划与全部完成判断使用材料进度，而不是战斗次数。"""
    finished = _material_plan(goal=2, counts={'特化以太芯片': 2})
    unfinished = _material_plan(goal=2, counts={'特化以太芯片': 1})
    config = _make_config([finished, unfinished])

    assert config.get_next_plan() is unfinished
    assert config.all_plan_finished() is False

    unfinished.material_counts['特化以太芯片'] = 2

    assert config.get_next_plan() is None
    assert config.all_plan_finished() is True


def test_loop_reset_keeps_material_goal_finished() -> None:
    """循环执行只重置按次数计划，不清空已经达成的材料目标。"""
    material = _material_plan(goal=2, counts={'特化以太芯片': 2})
    times = ChargePlanItem(run_times=3, plan_times=1)
    config = _make_config([material, times])

    config.reset_plans()

    assert material.material_counts == {'特化以太芯片': 2}
    assert times.run_times == 0
    config.save.assert_called_once()


def test_daily_reset_keeps_material_progress() -> None:
    """每日重置只清零战斗次数，不清空跨天累计的材料。"""
    material = _material_plan(counts={'特化以太芯片': 4})
    material.run_times = 3
    config = _make_config([material])
    config.data = {'daily_reset_plan_times': True, 'last_daily_reset_dt': '2026-08-01'}

    assert config.try_reset_plan_times_by_dt('2026-08-02') is True
    assert material.run_times == 0
    assert material.material_counts == {'特化以太芯片': 4}


def test_add_plan_material_counts_merges_and_saves() -> None:
    """一场战斗的多个材料数量一次合并并保存。"""
    plan = _material_plan(counts={'特化以太芯片': 4})
    config = _make_config([plan])

    updated = config.add_plan_material_counts(
        plan,
        {'特化以太芯片': 1, '进阶以太芯片': 12},
    )

    assert updated is True
    assert plan.material_counts == {
        '特化以太芯片': 5,
        '进阶以太芯片': 12,
    }
    config.save.assert_called_once()


def test_add_plan_material_counts_finds_plan_without_positive_count() -> None:
    """找到计划但没有正数可合并时，不误报为计划不存在。"""
    plan = _material_plan(counts={'特化以太芯片': 4})
    config = _make_config([plan])

    found = config.add_plan_material_counts(
        plan,
        {'特化以太芯片': 0, '进阶以太芯片': -1},
    )

    assert found is True
    assert plan.material_counts == {'特化以太芯片': 4}
    config.save.assert_not_called()


def test_material_fields_round_trip_in_dict() -> None:
    """材料模式字段会写入配置并可重新读取。"""
    original = _material_plan(
        goal=100,
        counts={'特化以太芯片': 23},
        include_synthesis=True,
    )

    restored = ChargePlanItem.from_dict(original.to_dict())

    assert restored.run_mode == original.run_mode
    assert restored.target_material_name == '特化以太芯片'
    assert restored.target_material_count == 100
    assert restored.material_counts == {'特化以太芯片': 23}
    assert restored.include_synthesis is True


def test_loop_with_only_finished_material_plan_ends_cleanly(
    test_context: TestContext,
) -> None:
    """只有已达成材料目标时，即使开启循环也正常结束而不是报无计划。"""
    material = _material_plan(goal=2, counts={'特化以太芯片': 2})
    config = _make_config([material])
    config.data = {'loop': True}
    app = ChargePlanApp(test_context)
    app.config = config

    result = app.find_next_plan()

    assert result.is_success
    assert result.status == ChargePlanApp.STATUS_ROUND_FINISHED
