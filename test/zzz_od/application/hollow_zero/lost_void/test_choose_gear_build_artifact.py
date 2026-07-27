"""LostVoidChooseGear._build_artifact_from_ocr_name 武备 OCR 构造测试。

按 testing methodology §5:OCR 文本 -> ``(LostVoidArtifact | None, is_primary)`` 的
解析逻辑同质,使用 ``@pytest.mark.parametrize`` + 数据表(ids=)统一驱动。

源码实际行为(已读 ``lost_void_choose_gear.py`` 确认):
- 实例方法(非静态),需 ``LostVoidChooseGear(test_context)``。
- normalize:strip + ``【``->``[``、``】``->``]``。
- 正则 ``\\[(.+?)\\](.+)$`` 必须形如 ``[分类]名称``,名称非空。
- 分类再修复 OCR 错字(``昇常``->``异常``)并按 ``：`` / ``:`` 切分取首段。

武备选择仅接受 ``[分类]名称`` 结构,其他 OCR 结果直接丢弃(返回 ``(None, False)``)。
"""
import pytest
from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_gear import (
    LostVoidChooseGear,
)


def _setup_op(test_context: TestContext) -> LostVoidChooseGear:
    test_context.lost_void.load_artifact_data()
    return LostVoidChooseGear(test_context)


def _build(test_context: TestContext, ocr_text: str) -> tuple:
    """构造 op 并调用,返回 (artifact|None, is_primary)。"""
    op = _setup_op(test_context)
    return op._build_artifact_from_ocr_name(ocr_text)


def test_empty_string(test_context: TestContext) -> None:
    """空串 -> (None, False)。"""
    art, is_primary = _build(test_context, '')
    assert art is None
    assert is_primary is False


def test_only_brackets_no_name(test_context: TestContext) -> None:
    """``[异常]`` 括号后无名称 -> (None, False)。"""
    art, is_primary = _build(test_context, '[异常]')
    assert art is None
    assert is_primary is False


def test_no_brackets(test_context: TestContext) -> None:
    """无 ``[]`` 结构的文本 -> (None, False)。"""
    art, is_primary = _build(test_context, '异常：xxx')
    assert art is None
    assert is_primary is False

    art, is_primary = _build(test_context, '无括号文本')
    assert art is None
    assert is_primary is False


# 有 [分类]名称 结构的用例:逻辑同质,参数化
# (ocr_text, expected_category, expected_name)
VALID_CASES: list[tuple[str, str, str]] = [
    ('[异常]xxx', '异常', 'xxx'),              # 半角括号
    ('【异常】xxx', '异常', 'xxx'),             # 全角括号(自动归一化为半角)
    ('[异常：yyy]xxx', '异常', 'xxx'),          # 分类含冒号 -> 按冒号切分取首段
    ('[异常:yyy]xxx', '异常', 'xxx'),           # 半角冒号切分
]


@pytest.mark.parametrize(
    'ocr_text, category, name', VALID_CASES,
    ids=[c[0] for c in VALID_CASES],
)
def test_valid_bracketed_name(
    test_context: TestContext, ocr_text: str, category: str, name: str,
) -> None:
    """``[分类]名称`` -> (artifact, True),分类/名称正确,武备标记。"""
    art, is_primary = _build(test_context, ocr_text)
    assert art is not None, f'{ocr_text}: 应构造出 artifact'
    assert is_primary is True
    assert art.category == category, f'{ocr_text}: category'
    assert art.name == name, f'{ocr_text}: name'
    assert art.level == '?'
    assert art.is_gear is True
    # display_name: 分类不在 ['卡牌', '无详情'] 时,显示为 [分类]名称
    assert art.display_name == f'[{category}]{name}'
