"""ChoosePredefinedTeam 编队名匹配 match_team_name 测试。

背景:出战画面编队列表一页只显示约6个编队,目标编队(如 编队8)不在当前页时,
原 ``difflib.get_close_matches``(cutoff 0.6)会把「编队1」按 0.67 相似度当成命中
→ 点错编队,且永远不会触发翻页(翻页只在完全没匹配时走)。

规则:去空白后先精确匹配;模糊匹配(>=0.6)排除「非数字部分相同、数字部分不同」
的候选(那是另一支编队);找不到返回 None 让调用方走翻页。
"""
from zzz_od.operation.choose_predefined_team import match_team_name

# 2026-08-20 实机日志中出战画面第一页的真实OCR结果
PAGE1_OCR = ['编队1', '3/3', '编队 2', '1P', '2P', '3P', 'BANGBOO', '☆',
             '+ SELECT', '编队3', '编队4', '编队5', '2/2', '编队6', '预备出战']


def test_target_not_on_page_returns_none() -> None:
    """目标编队不在当前页 → 返回 None(触发翻页),不被相邻编号顶包。"""
    assert match_team_name('编队8', PAGE1_OCR) is None
    assert match_team_name('编队12', PAGE1_OCR) is None


def test_exact_match() -> None:
    """精确命中。"""
    assert match_team_name('编队3', PAGE1_OCR) == '编队3'


def test_whitespace_tolerant_match() -> None:
    """OCR带空格也能命中(编队 2 vs 编队2)。"""
    assert match_team_name('编队2', PAGE1_OCR) == '编队 2'


def test_fuzzy_match_for_custom_names() -> None:
    """自定义编队名允许模糊匹配兜底OCR错字。"""
    assert match_team_name('主C强攻队', ['主C强攻以', '预备出战']) == '主C强攻以'


def test_different_custom_names_no_match() -> None:
    """完全不同的名字不能命中。"""
    assert match_team_name('异常队', ['击破队', '预备出战']) is None
