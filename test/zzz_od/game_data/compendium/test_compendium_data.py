"""``assets/game_data/compendium_data.yml`` 数据完整性:关卡名唯一 + 别名不撞名 + 新关卡可被体力计划使用。

**为什么要锁「关卡名全库唯一」**:``CompendiumService.get_same_category_mission_type_list(name)``
拿关卡名在**全库**找第一个命中,返回**那个 category** 的完整列表;
``CompendiumChooseMissionType`` 再用这个列表做 OCR 候选匹配 + 判断滑动方向。
同一个关卡名若挂在两个 category 下,传送到第二个 category 的关卡会拿到第一个 category 的列表
→ 候选名单错 → 匹配不到「前往」→ 一直往下滑,计划卡死重试。

**为什么规则是「白名单」而不是「绝不重名」**:现有数据里有两类跨分类共用的伪条目/同名条目,
它们不构成上面那个失败模式,所以显式登记为允许值而不是放宽断言:

- ``代理人方案培养``:每个分类都挂一条,表示「按代理人计划进入」;
  ``CompendiumChooseMissionType.choose_mission_type`` 靠 ``is_agent_plan`` 提前分支,不会走列表匹配。
- ``迷失之地``:``作战`` tab 下 ``周期征讨``(纯入口)与 ``零号空洞``(含子关卡)各一条。

新增跨分类重名会 fail 并打印冲突位置,便于判断是「漏放白名单」还是「真的填错了名字」。
"""

import collections

import pytest
from test.conftest import TestContext

from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.application.notorious_hunt.notorious_hunt_config import (
    NotoriousHuntConfig,
    NotoriousHuntLevelEnum,
)

# 允许跨分类重名的关卡名(原因见模块 docstring);新增重名必须先确认不属于上面的失败模式
_CROSS_CATEGORY_ALLOWED: set[str] = {'代理人方案培养', '迷失之地'}


def _all_mission_types(test_context: TestContext) -> list[tuple[str, str, str]]:
    """返回全部关卡类型 ``(tab_name, category_name, mission_type_name)``。"""
    result: list[tuple[str, str, str]] = []
    for tab in test_context.compendium_service.data.tab_list:
        for category in tab.category_list:
            for mission_type in category.mission_type_list:
                result.append((tab.tab_name, category.category_name, mission_type.mission_type_name))
    return result


def test_data_loaded_and_name_not_empty(test_context: TestContext) -> None:
    """数据能加载且关卡名非空(空名会让 OCR 匹配退化到随机命中)。"""
    mission_types = _all_mission_types(test_context)
    assert mission_types, 'compendium_data.yml 未加载到任何关卡'

    empty = [i for i in mission_types if not i[2].strip()]
    assert not empty, f'存在空关卡名: {empty}'


def test_mission_type_name_unique_within_category(test_context: TestContext) -> None:
    """同一分类内关卡名唯一(列表内重名会让 target_idx 命中错误的那条,划到哪条都可能点错)。"""
    counter: collections.Counter[tuple[str, str, str]] = collections.Counter(
        (tab_name, category_name, mission_type_name)
        for tab_name, category_name, mission_type_name in _all_mission_types(test_context)
    )

    duplicated = [key for key, count in counter.items() if count > 1]
    assert not duplicated, f'同一分类内关卡名重复 (tab, category, name): {duplicated}'


def test_cross_category_duplicate_name_is_allowlisted(test_context: TestContext) -> None:
    """跨分类重名必须都在白名单内(否则 get_same_category_mission_type_list 会返回错分类的列表)。"""
    positions: dict[str, list[str]] = collections.defaultdict(list)
    for tab_name, category_name, mission_type_name in _all_mission_types(test_context):
        positions[mission_type_name].append(f'{tab_name}/{category_name}')

    duplicates = {name: where for name, where in positions.items() if len(where) > 1}
    unexpected = {name: where for name, where in duplicates.items() if name not in _CROSS_CATEGORY_ALLOWED}
    assert not unexpected, (
        f'出现未登记的跨分类重名关卡: {unexpected};'
        f'确认无冲突后加进 _CROSS_CATEGORY_ALLOWED,或改名'
    )


def test_alias_list_not_collide_with_mission_type_name(test_context: TestContext) -> None:
    """别名不与任何关卡名重复(别名声明的本意是 OCR 识别不到真名时兜底,撞名会让映射指向别的关卡)。"""
    names = {name for _, _, name in _all_mission_types(test_context)}

    collisions: list[str] = []
    for tab in test_context.compendium_service.data.tab_list:
        for category in tab.category_list:
            for mission_type in category.mission_type_list:
                own = {mission_type.mission_type_name, *mission_type.alias_list}
                for alias in mission_type.alias_list:
                    if alias in names and alias not in own:
                        collisions.append(f'{alias}(挂在 {tab.tab_name}/{category.category_name})')

    assert not collisions, f'别名与其它关卡名冲突: {collisions}'


@pytest.mark.parametrize(
    'category_name, mission_type_name, level',
    [
        # 3.2 新增:专业挑战室「征服者」
        ('专业挑战室', '「征服者」', '默认等级'),
        # 3.2 新增:恶名狩猎 库萨里库
        ('恶名狩猎', '库萨里库', NotoriousHuntLevelEnum.DEFAULT.value.value),
    ],
)
def test_new_level_reachable_and_usable(
    test_context: TestContext,
    category_name: str,
    mission_type_name: str,
    level: str,
) -> None:
    """新关卡:名字能解析到本分类 + 能被体力计划/恶名狩猎配置写入校验放行。

    名字解析到本分类是传送的前提:``get_same_category_mission_type_list`` 返回的必须是**本分类**的列表
    (用 ``is`` 比较列表对象,比只比对名字更严格)。

    ``mission_name`` 显式传 ``None``:``validate_item`` 对没有子关卡的分类(专业挑战室)要求 ``mission_name`` 为空,
    而 ``ChargePlanItem`` 的默认值是非空的 ``'调查专项'``(实战模拟室用),所以带默认值建 item 会被判不合法。
    """
    category = test_context.compendium_service.get_category_data('训练', category_name)
    assert category is not None, f'训练 tab 缺分类 {category_name}'

    mission_type = test_context.compendium_service.get_mission_type_data('训练', category_name, mission_type_name)
    assert mission_type is not None, f'{category_name} 缺关卡 {mission_type_name}'

    assert test_context.compendium_service.get_same_category_mission_type_list(mission_type_name) is category.mission_type_list, (
        f'{mission_type_name} 解析到的列表不是 {category_name} 的列表 → 传送会拿错候选名单'
    )

    item = ChargePlanItem(
        category_name=category_name,
        mission_type_name=mission_type_name,
        mission_name=None,
        level=level,
        auto_battle_config='全配队通用',
        predefined_team_idx=-1,
    )
    if category_name == '恶名狩猎':
        assert NotoriousHuntConfig.validate_item(test_context, item) is None
    else:
        assert ChargePlanConfig.validate_item(test_context, item) is None
