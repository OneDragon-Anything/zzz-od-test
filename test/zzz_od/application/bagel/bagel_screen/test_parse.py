from __future__ import annotations

import pytest

from zzz_od.application.bagel.bagel_screen import parse_capacity_pair, parse_filter_count


@pytest.mark.parametrize('text,expected', [
    ('全部(235/280)', (235, 280)),
    ('全部 (259/280)', (259, 280)),
    ('全部(280/280)', (280, 280)),
    ('乱码', None),
    ('全部(300/280)', None),
    ('全部(0/0)', None),
])
def test_parse_capacity_pair(text: str, expected: tuple[int, int] | None) -> None:
    """占用与容量成对解析；满仓 280/280 有效，颠倒或零容量拒绝。"""
    assert parse_capacity_pair(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('符合以上条件的道具数量:0', 0),
    ('符合以上条件的道具数量：12', 12),
    ('数量:3', 3),
    ('符合以上条件的道具数量0', 0),
    ('乱码', None),
    ('12', None),
])
def test_parse_filter_count(text: str, expected: int | None) -> None:
    """筛选件数必须带数量或「符合」上下文，不能把旁边数字当成件数。"""
    assert parse_filter_count(text) == expected
