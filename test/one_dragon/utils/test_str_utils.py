"""str_utils 纯函数测试。

OCR 文本匹配几乎都经过这里（``find_by_lcs`` / ``find_best_match_by_*`` / ``find_in_list_with_fuzzy``），
按等价类取代表值，阈值处取边界值（恰好等于阈值算命中）。
"""

from __future__ import annotations

import pytest

from one_dragon.utils import str_utils


@pytest.mark.parametrize(
    ('source', 'target', 'ignore_case', 'expected'),
    [
        ('abc', 'b', False, 1),
        ('ABC', 'b', False, -1),
        ('ABC', 'b', True, 1),
        (None, 'b', False, -1),
        ('abc', None, False, -1),
    ],
    ids=['命中', '大小写敏感未命中', '忽略大小写命中', 'source为空', 'target为空'],
)
def test_find(source: str | None, target: str | None, ignore_case: bool, expected: int) -> None:
    assert str_utils.find(source, target, ignore_case=ignore_case) == expected


@pytest.mark.parametrize(
    ('source', 'target', 'percent', 'ignore_case', 'expected'),
    [
        ('领取奖励', '领取奖励', 0.3, True, True),
        ('领取奖励', '领取', 0.5, True, True),  # lcs=2 = 4*0.5 边界 命中
        ('领取奖励', '领', 0.5, True, False),  # lcs=1 < 2
        ('ABCD', 'abcd', 1, True, True),
        ('ABCD', 'abcd', 1, False, False),
        ('', 'abc', 0.3, True, False),
        ('abc', '', 0.3, True, False),
        (None, 'abc', 0.3, True, False),
    ],
    ids=['完全一致', '恰好等于阈值', '低于阈值', '忽略大小写', '区分大小写', 'source空串', 'target空串', 'source为None'],
)
def test_find_by_lcs(source: str | None, target: str, percent: float, ignore_case: bool, expected: bool) -> None:
    assert str_utils.find_by_lcs(source, target, percent=percent, ignore_case=ignore_case) == expected


@pytest.mark.parametrize(
    ('s1', 's2', 'expected'),
    [('abcde', 'ace', 3), ('abc', 'def', 0), ('', 'abc', 0)],
    ids=['子序列', '无公共', '空串'],
)
def test_longest_common_subsequence_length(s1: str, s2: str, expected: int) -> None:
    assert str_utils.longest_common_subsequence_length(s1, s2) == expected


@pytest.mark.parametrize(
    ('v', 'expected'),
    [('体力 120/240', 120240), ('-35', 35), ('无数字', None)],
    ids=['混合文本', '忽略符号', '无数字返回err'],
)
def test_get_positive_digits(v: str, expected: int | None) -> None:
    assert str_utils.get_positive_digits(v) == expected


@pytest.mark.parametrize(
    ('v', 'err', 'expected'),
    [('倍率 1.5x', None, 1.5), ('abc', -1, -1), ('1.2.3', 0, 0)],
    ids=['提取小数', '无数字返回err', '非法小数返回err'],
)
def test_get_positive_float(v: str, err: int | None, expected: float | None) -> None:
    assert str_utils.get_positive_float(v, err=err) == expected


@pytest.mark.parametrize(
    ('word', 'targets', 'threshold', 'expected'),
    [
        ('前往挑战', ['挑战', '前往'], None, 0),  # 两者 lcs 比例都是 1 取先出现的
        ('挑战', ['挑战开始', '挑战'], None, 1),  # 比例更高者胜
        ('挑', ['挑战开始'], 0.5, None),  # 1/4 < 0.5
        ('xyz', ['挑战'], None, None),  # 无公共字符
    ],
    ids=['比例相同取先', '比例高者胜', '低于阈值', '无匹配'],
)
def test_find_best_match_by_lcs(word: str, targets: list[str], threshold: float | None,
                                expected: int | None) -> None:
    assert str_utils.find_best_match_by_lcs(word, targets, lcs_percent_threshold=threshold) == expected


@pytest.mark.parametrize(
    ('target', 'word_list', 'expected'),
    [
        ('确认', ['取消', '确认'], 1),  # 精确匹配优先
        ('确认键', ['取消', '确认'], 1),  # 模糊兜底
        ('完全不同', ['取消', '确认'], None),
    ],
    ids=['精确匹配', '模糊匹配', '无匹配'],
)
def test_find_in_list_with_fuzzy(target: str, word_list: list[str], expected: int | None) -> None:
    assert str_utils.find_in_list_with_fuzzy(target, word_list) == expected


@pytest.mark.parametrize(
    ('list1', 'list2', 'expected'),
    [
        (['零号空洞', '式舆防卫战'], ['式舆防卫站', '其他'], (1, 0)),
        (['abc'], ['xyz'], (None, None)),
    ],
    ids=['双向最相似', '无匹配'],
)
def test_find_most_similar(list1: list[str], list2: list[str], expected: tuple[int | None, int | None]) -> None:
    assert str_utils.find_most_similar(list1, list2) == expected


@pytest.mark.parametrize(
    ('s', 'expected'),
    [('abc中文', True), ('abc123', False), ('', False)],
    ids=['含中文', '无中文', '空串'],
)
def test_with_chinese(s: str, expected: bool) -> None:
    assert str_utils.with_chinese(s) == expected


@pytest.mark.parametrize(
    ('s1', 's2', 'expected'),
    [('kitten', 'sitting', 3), ('abc', 'abc', 0), ('', 'abc', 3), ('ab', 'abcd', 2)],
    ids=['经典样例', '相同', '空串', '短串在前'],
)
def test_levenshtein_distance(s1: str, s2: str, expected: int) -> None:
    assert str_utils.levenshtein_distance(s1, s2) == expected


@pytest.mark.parametrize(
    ('ocr_text', 'targets', 'threshold', 'expected_text', 'expected_score'),
    [
        ('确认', ['确认', '取消'], 0.5, '确认', 1.0),
        ('确认键', ['确认', ''], 0.5, '确认', pytest.approx(2 / 3)),  # 跳过空目标
        ('ab', ['cd'], 0.5, None, 0.0),  # 低于阈值 返回最高分
        ('ab', ['ac'], 0.5, 'ac', 0.5),  # 恰好等于阈值算命中
        ('', ['确认'], 0.5, None, 0.0),
        ('确认', [], 0.5, None, 0.0),
    ],
    ids=['完全一致', '跳过空目标', '低于阈值', '恰好等于阈值', 'OCR为空', '目标为空'],
)
def test_find_best_match_by_similarity(ocr_text: str, targets: list[str], threshold: float,
                                       expected_text: str | None, expected_score: float) -> None:
    text, score = str_utils.find_best_match_by_similarity(ocr_text, targets, threshold=threshold)
    assert text == expected_text
    assert score == expected_score


@pytest.mark.parametrize(
    ('target', 'ocr_list', 'expected'),
    [
        ('C', ['A', 'B'], True),  # 画面里是目标之前的项 → 目标在后面
        ('C', ['D', 'E'], False),  # 画面里只有目标之后的项
        ('A', ['B'], False),  # 目标排第一 前面没有项
        ('X', ['A'], False),  # 目标不在有序列表
    ],
    ids=['目标在后', '目标在前', '目标是首项', '目标不在列表'],
)
def test_is_target_after_ocr_list(target: str, ocr_list: list[str], expected: bool) -> None:
    assert str_utils.is_target_after_ocr_list(target, ['A', 'B', 'C', 'D', 'E'], ocr_list) == expected


@pytest.mark.parametrize(
    ('v', 'expected'),
    [(' 开 始\t战斗\n', '开始战斗'), (None, '')],
    ids=['移除各类空白', 'None返回空串'],
)
def test_remove_whitespace(v: str | None, expected: str) -> None:
    assert str_utils.remove_whitespace(v) == expected
