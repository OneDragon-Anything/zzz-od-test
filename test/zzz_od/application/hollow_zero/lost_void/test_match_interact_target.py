"""match_interact_target 纯函数分支测试。

按 testing methodology §5:本函数是「同一识别逻辑的不同输入分支」,逻辑同质,
因此使用 ``@pytest.mark.parametrize`` + 数据表(ids=)统一驱动。

覆盖分支(读 ``lost_void_interact_target_const.py`` 源码确认):
- 空 / 去 ``<>`` 后空 -> None
- 入口(带 ``<>`` 或纯文本) -> ``is_entry=True``
- NPC -> ``is_npc=True`` 且 icon 固定为 ``感叹号``
- 代理人 -> ``is_agent=True``
- BOSS -> ``is_entry=True`` 且 icon = ``LostVoidRegionType.BOSS.value.value``
- 不匹配垃圾串(difflib cutoff=0.6) -> None
"""
import pytest
from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_interact_target_const import (
    LostVoidBoss,
    LostVoidInteractNPC,
    match_interact_target,
)
from zzz_od.game_data.agent import AgentEnum

# 真实 enum 成员值(避免硬编码中文出错)
_ENTRY_TEXT = LostVoidRegionType.ENTRY.value.value  # '入口'
_BOSS_ICON = LostVoidRegionType.BOSS.value.value  # '战斗-终结之役'
_NPC_TEXT = LostVoidInteractNPC.MA_LIN.value  # '玛琳'
_AGENT_TEXT = AgentEnum.ANBY.value.agent_name  # '安比'
_BOSS_TEXT = LostVoidBoss.SHENG_GUI.value  # '终结之役·牲鬼'


def test_empty_string_returns_none(test_context: TestContext) -> None:
    """空字符串应返回 None。"""
    assert match_interact_target(test_context, '') is None


def test_only_brackets_returns_none(test_context: TestContext) -> None:
    """仅含 ``<>`` 去除后为空,应返回 None。"""
    assert match_interact_target(test_context, '<>') is None


# 入口分支:用真实入口文本,参数化覆盖「带括号」「纯文本」两种输入
@pytest.mark.parametrize(
    'ocr_text',
    [f'<{_ENTRY_TEXT}>', _ENTRY_TEXT],
    ids=['entry_with_brackets', 'entry_plain'],
)
def test_match_entry(test_context: TestContext, ocr_text: str) -> None:
    """命中入口 -> is_entry=True,name/icon 均为入口文本。"""
    target = match_interact_target(test_context, ocr_text)
    assert target is not None
    assert target.is_entry is True
    assert target.is_npc is False
    assert target.is_agent is False
    assert target.name == _ENTRY_TEXT
    assert target.icon == _ENTRY_TEXT


def test_match_npc(test_context: TestContext) -> None:
    """命中 NPC(如玛琳) -> is_npc=True,icon 固定为「感叹号」。"""
    target = match_interact_target(test_context, _NPC_TEXT)
    assert target is not None
    assert target.is_npc is True
    assert target.is_entry is False
    assert target.is_agent is False
    assert target.name == _NPC_TEXT
    assert target.icon == '感叹号'


def test_match_agent(test_context: TestContext) -> None:
    """命中代理人(如安比) -> is_agent=True,name 为 agent_name,icon 为「感叹号」。"""
    target = match_interact_target(test_context, _AGENT_TEXT)
    assert target is not None
    assert target.is_agent is True
    assert target.is_entry is False
    assert target.is_npc is False
    assert target.name == _AGENT_TEXT
    assert target.icon == '感叹号'


def test_match_boss(test_context: TestContext) -> None:
    """命中 BOSS(如终结之役·牲鬼) -> is_entry=True,icon 为 BOSS 区域类型文本。"""
    target = match_interact_target(test_context, _BOSS_TEXT)
    assert target is not None
    assert target.is_entry is True
    assert target.is_npc is False
    assert target.is_agent is False
    assert target.name == _BOSS_TEXT
    assert target.icon == _BOSS_ICON


def test_no_match_garbage(test_context: TestContext) -> None:
    """与全部目标差异过大的垃圾串(difflib cutoff=0.6)应返回 None。"""
    # 纯 ASCII + 无关中文,确保与所有中文目标相似度低于 0.6
    assert match_interact_target(test_context, 'ABCDEFGzzzzz') is None
