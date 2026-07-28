"""UpdatePriorityOperation._extract_priority_category_from_text 静态方法测试。

按 testing methodology §5:正则解析「[分类:xxx]名称」分类的逻辑同质,各分支仅输入与
期望不同,使用 ``@pytest.mark.parametrize`` + 数据表(ids=)统一驱动。

源码实际行为(已读 ``update_priority_operation.py`` 确认正则):
正则 ``[\\[【]\\s*([^:\\]】：]+)\\s*[:：]`` —— 必须有 ``[`` 或 ``【`` 开头,
分类字符组内排除 ``:`` ``]`` ``】`` ``:``,且分类后必须紧跟 ``:`` 或 ``：``。

注意(与字面预期不一致之处,按源码实际行为写):
- ``[异常]xxx``(括号内无冒号)-> None(不是「异常」),因为冒号是必需的。
- ``【异常】xxx``(中文括号无冒号)-> None,同理。
"""
import pytest

from zzz_od.application.hollow_zero.lost_void.operation.update_priority_operation import (
    UpdatePriorityOperation,
)

# (输入文本, 期望分类)
CASES: list[tuple[str, str | None]] = [
    ('', None),                          # 空串
    ('[防护：斗盾]霸气驰援', '防护'),     # [中文分类：] 冒号在括号内
    ('【异常：xxx】yyy', '异常'),         # 【中文分类：】 全角括号 + 冒号
    ('[异常:yyy]xxx', '异常'),            # 半角冒号也识别
    ('[防护:斗盾]霸气驰援', '防护'),      # 半角冒号
    ('没有括号的文本', None),             # 无括号
    ('防护：斗盾', None),                 # 有冒号但无括号
    ('[a]xxx', None),                     # 有括号但括号内无冒号
    ('[异常]xxx', None),                  # 括号内无冒号 -> None(冒号必需)
    ('【异常】xxx', None),                # 中文括号无冒号 -> None(冒号必需)
]


@pytest.mark.parametrize(
    'text, expected', CASES,
    ids=[f'{c[0][:12]!r}' if len(c[0]) > 0 else 'empty' for c in CASES],
)
def test_extract_priority_category(text: str, expected: str | None) -> None:
    """静态方法直接调用,无需实例化 op。"""
    actual = UpdatePriorityOperation._extract_priority_category_from_text(text)
    assert actual == expected, f'text={text!r} expected={expected!r} actual={actual!r}'
