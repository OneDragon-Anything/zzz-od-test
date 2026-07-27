"""LostVoidRunLevel.init_for_region_type 区域类型路由测试。

按 testing methodology 动作一:init_for_region_type 按 ``self.region_type``(LostVoidRegionType)
+ ``self.click_challenge_confirm`` / ``self.boss_pre_battle`` 标志,路由到「战斗区域」或
「非战斗区域」两种 status。

纯配置/标志测试,无画面依赖:
- 直接构造 ``LostVoidRunLevel`` 实例后,赋值 ``op.region_type`` / 标志位,调
  ``init_for_region_type`` 断言 ``result.status``。
- CHANLLENGE_TIME_TRAIL + click_challenge_confirm=True 还需断言标志位被复位为 False。
"""
import pytest
from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)


def _setup_op(test_context: TestContext) -> LostVoidRunLevel:
    """构造一个 ENTRY 类型的 LostVoidRunLevel 实例,前置加载武备/挑战配置。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    return LostVoidRunLevel(test_context, LostVoidRegionType.ENTRY)


# 非战斗类区域:status 恒为「非战斗区域」(不依赖标志位)
NON_BATTLE_REGIONS: list[LostVoidRegionType] = [
    LostVoidRegionType.ENTRY,
    LostVoidRegionType.COMBAT_RESONIUM,
    LostVoidRegionType.COMBAT_GEAR,
    LostVoidRegionType.COMBAT_COIN,
    LostVoidRegionType.CHANLLENGE_FLAWLESS,
    LostVoidRegionType.ENCOUNTER,
    LostVoidRegionType.PRICE_DIFFERENCE,
    LostVoidRegionType.REST,
    LostVoidRegionType.BANGBOO_STORE,
    LostVoidRegionType.FRIENDLY_TALK,
    # CHANLLENGE_ENEMY_TRAIL 未在 switch 中路由,落到末尾兜底分支返回「非战斗区域」
    LostVoidRegionType.CHANLLENGE_ENEMY_TRAIL,
]


@pytest.mark.parametrize('region_type', NON_BATTLE_REGIONS,
                         ids=[r.name for r in NON_BATTLE_REGIONS])
def test_non_battle_region(test_context: TestContext,
                           region_type: LostVoidRegionType) -> None:
    """非战斗类区域:无论标志位如何,status 恒为「非战斗区域」。"""
    op = _setup_op(test_context)
    op.region_type = region_type
    result = op.init_for_region_type()
    assert result.is_success
    assert result.status == '非战斗区域'


def test_time_trail_with_click_confirm(test_context: TestContext) -> None:
    """挑战-限时 + click_challenge_confirm=True → 「战斗区域」,标志位复位 False。"""
    op = _setup_op(test_context)
    op.region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
    op.click_challenge_confirm = True
    result = op.init_for_region_type()
    assert result.is_success
    assert result.status == '战斗区域'
    assert op.click_challenge_confirm is False, 'click_challenge_confirm 应被复位为 False'


def test_time_trail_without_click_confirm(test_context: TestContext) -> None:
    """挑战-限时 + click_challenge_confirm=False → 「非战斗区域」。"""
    op = _setup_op(test_context)
    op.region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
    op.click_challenge_confirm = False
    result = op.init_for_region_type()
    assert result.is_success
    assert result.status == '非战斗区域'


def test_elite_is_battle(test_context: TestContext) -> None:
    """战斗-道中危机(ELITE)恒为「战斗区域」。"""
    op = _setup_op(test_context)
    op.region_type = LostVoidRegionType.ELITE
    result = op.init_for_region_type()
    assert result.is_success
    assert result.status == '战斗区域'


def test_boss_pre_battle_true(test_context: TestContext) -> None:
    """战斗-终结之役 + boss_pre_battle=True → 「非战斗区域」(先处理战前交互)。"""
    op = _setup_op(test_context)
    op.region_type = LostVoidRegionType.BOSS
    op.boss_pre_battle = True
    result = op.init_for_region_type()
    assert result.is_success
    assert result.status == '非战斗区域'


def test_boss_pre_battle_false(test_context: TestContext) -> None:
    """战斗-终结之役 + boss_pre_battle=False → 「战斗区域」。"""
    op = _setup_op(test_context)
    op.region_type = LostVoidRegionType.BOSS
    op.boss_pre_battle = False
    result = op.init_for_region_type()
    assert result.is_success
    assert result.status == '战斗区域'


def test_boss_default_pre_battle_is_true(test_context: TestContext) -> None:
    """BOSS 实例化时 boss_pre_battle 默认 True(source: region_type == BOSS)。"""
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    op = LostVoidRunLevel(test_context, LostVoidRegionType.BOSS)
    assert op.boss_pre_battle is True
