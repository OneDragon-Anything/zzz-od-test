"""LostVoidBangbooStore.check_store_type 商店类型识别测试。

按 testing methodology 动作一:``check_store_type`` 按「标识-金币」/「标识-血量」模板命中
→ 设 ``store_type``。本文件用 ``迷失之地-邦布商店`` 的 fixture 覆盖金币商店分支(GREEN),
并圈定血量商店分支(RED,fixture 待采)。

源码行为(已读 ``lost_void_bangboo_store.py`` 的 ``check_store_type`` 确认):
- ``round_by_find_area`` 命中时 status = area_name,因此命中「标识-金币」→
  ``self.store_type = '标识-金币'``;命中「标识-血量」→ ``self.store_type = '标识-血量'``。
- 金币商店已有 fixture(``商店.webp``)→ GREEN;血量商店罕见,缺 fixture 时自动 skip(``has_screen``),采到恢复 GREEN。
"""
import pytest
from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_bangboo_store import (
    LostVoidBangbooStore,
)


def test_store_type_gold(test_context: TestContext) -> None:
    """金币商店:命中「标识-金币」→ store_type='标识-金币',返回 round_success(已有 fixture)。"""
    op = LostVoidBangbooStore(test_context)
    test_context.mock_screen('迷失之地-邦布商店', '商店')
    op.screenshot()

    result = op.check_store_type()

    assert op.store_type == '标识-金币'
    assert result.is_success
    assert result.status == '标识-金币'


def test_store_type_blood(test_context: TestContext) -> None:
    """血量商店:命中「标识-血量」→ store_type='标识-血量'。

    血量商店子态罕见,fixture (``血量商店.webp``) 缺时自动 skip(``has_screen`` 判存);
    采集后补 fixture 即自动恢复 GREEN。
    """
    if not test_context.has_screen('迷失之地-邦布商店', '血量商店'):
        pytest.skip('缺 fixture: 迷失之地-邦布商店/血量商店,罕见态待 run 采集')
    op = LostVoidBangbooStore(test_context)
    test_context.mock_screen('迷失之地-邦布商店', '血量商店')
    op.screenshot()

    result = op.check_store_type()

    assert op.store_type == '标识-血量'
    assert result.is_success
    assert result.status == '标识-血量'
