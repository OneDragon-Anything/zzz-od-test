"""prompts 模块引导内容的单元测试(instructions / guide mode 分流)。

覆盖三通道的内容正确性:
- ``render_instructions``:server 级共通操作哲学(握手注入客户端 system prompt)。
- ``list_prompt_guides`` / ``render_prompt_guide``:help 目录 + 模式分流(user/dev)。
"""

from zzz_od.backend.mcp.prompts import (
    list_prompt_guides,
    render_instructions,
    render_prompt_guide,
)


# ===== instructions(server 级共通操作哲学)=====

def test_instructions_non_empty_with_key_phrases() -> None:
    """render_instructions 非空,含共通操作哲学关键短语(三件套/工具分类/pc_alt/dev 指针)。"""
    text = render_instructions()
    assert isinstance(text, str) and len(text) > 0
    assert '操作三件套' in text                       # 核心循环
    assert 'analyze_screen' in text and 'run_operation' in text   # 工具分类
    assert 'pc_alt' in text                          # 实机约束
    assert 'zzz_dev_validate_op' in text             # dev guide 指针


# ===== guide mode 分流(user/dev)=====

def test_guide_items_have_mode_field() -> None:
    """list_prompt_guides 每项含 mode 字段,值在 {user, dev},且两类都有。"""
    items = list_prompt_guides()
    modes = {item['mode'] for item in items}
    assert modes <= {'user', 'dev'}
    assert 'user' in modes and 'dev' in modes


def test_guide_has_dev_validate_op() -> None:
    """dev 模式含 zzz_dev_validate_op 项(开发者 op 验证)。"""
    items = list_prompt_guides()
    dev = [i for i in items if i['mode'] == 'dev']
    assert any(i['name'] == 'zzz_dev_validate_op' for i in dev)


def test_render_dev_guide_contains_battle_op_boundary() -> None:
    """render_prompt_guide('zzz_dev_validate_op') 含战斗 op 边界(dev 关键知识)。"""
    text = render_prompt_guide('zzz_dev_validate_op')
    assert '战斗 op 边界' in text
    assert 'run_operation' in text


def test_render_guide_unknown_name_hints_available() -> None:
    """未知 guide 名称 → 返回可用名称提示(含 zzz_dev_validate_op)。"""
    text = render_prompt_guide('not_a_guide')
    assert '未知指南' in text
    assert 'zzz_dev_validate_op' in text


def test_render_user_guide_still_works() -> None:
    """user 模式 guide(zzz_check_status)仍正常渲染(回归)。"""
    text = render_prompt_guide('zzz_check_status')
    assert 'get_run_status' in text


def test_render_standalone_app_guide_passes_app_id() -> None:
    """render_prompt_guide('zzz_run_standalone_app', app_id=...) 把 app_id 透传进文本。"""
    text = render_prompt_guide('zzz_run_standalone_app', app_id='foo_app')
    assert "app_id='foo_app'" in text
