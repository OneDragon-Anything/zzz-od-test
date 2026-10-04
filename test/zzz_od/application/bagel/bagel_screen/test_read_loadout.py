from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

import pytest
from test.harness.bagel_loadout import mock_loadout_ocr

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.application.bagel.bagel_screen import (
    complete_loadout,
    read_loadout,
    zero_loadout,
)

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('full_texts,crop_texts,expected,full_fallback', [
    (['装备', '0'], None, '0', False),
    (['装备', '1000'], None, '1000', False),
    (['0'], ['0'], '0', False),
    (['装备0'], ['装备', '0'], '0', False),
    (['装备'], ['装备', '@0'], '0', False),
    (['装备'], ['装备', '@1000'], '1000', False),
    (['装备', '0', '0'], ['装备', '0'], '0', False),
    (['装备', '0', '@500'], None, '', False),
    (['装备', '0', '500元'], None, '', False),
    (['装备'], ['装备', '0', '@500'], '', False),
    (['装备'], ['装备', '0', '1,000'], '', False),
    (['装备', '0', '500'], ['装备', '0'], '', False),
    (['@500'], ['装备', '@0'], '', False),
    ([], [], '', True),
    (['装备'], ['装备'], '', True),
    (['装备'], ['装备', '0', '0'], '', True),
    (['装备'], ['装备', '1000', '0'], '', True),
    (['装备'], ['装备', '@0', '#0'], '', True),
    (['装备'], ['装备', '@@@0'], '', True),
    (['装备'], ['O'], '', True),
])
def test_read_loadout_panel_then_crop(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    full_texts: list[str], crop_texts: list[str] | None, expected: str, full_fallback: bool,
) -> None:
    """面板须有标题和唯一数字，失败才裁完整标题条；无法确认不得当零。"""
    screen = test_context.load_screen('贝果-备战', '高危零携带-原生1080')
    ocr = mock_loadout_ocr(test_context, monkeypatch, '装备价值', full_texts, crop_texts)

    values = read_loadout(test_context, screen)

    assert values == {
        '武备价值': '0', '装备价值': expected, '道具价值': '0',
        '背包数量': '0/20', '安全箱数量': '0/5',
    }
    assert zero_loadout(values) is (expected == '0')
    assert ocr.call_args_list[0] == call(screen, rect=Rect(1000, 0, 1920, 1080), crop_first=True)
    assert ocr.call_count == 3 + (crop_texts is not None) + full_fallback
    rect = test_context.screen_loader.get_area('贝果-备战', '装备价值').pc_rect
    assert (call(screen, rect=rect, crop_first=False) in ocr.call_args_list) is full_fallback
    for name in ('背包数量', '安全箱数量'):
        area = test_context.screen_loader.get_area('贝果-备战', name)
        ocr.assert_any_call(screen, rect=area.pc_rect, crop_first=True, color_range=area.color_range)


@pytest.mark.parametrize('state,values', [
    ('clear_loadout_carried', ('270000', '160000', '78000', '2/50', '0/5')),
    ('clear_loadout_empty', ('0', '0', '0', '0/20', '0/5')),
    ('clear_loadout_tools_only', ('0', '0', '78000', '0/20', '0/5')),
])
def test_prepare_recording(test_context: TestContext, state: str, values: tuple[str, ...]) -> None:
    """归档画面识别五项；灰色空武备图案及左侧库存不得算携带物。"""
    screen = test_context.load_screen('贝果-备战', state)
    actual = read_loadout(test_context, screen)
    assert tuple(actual.values()) == values, actual
    assert complete_loadout(actual)


def test_dense_inventory_is_not_sent_to_ocr(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """实际识别录像画面，避免左侧大量库存文本增加每次核验的开销。"""
    screen = test_context.load_screen('贝果-备战', 'clear_loadout_dense_inventory').copy()
    matcher = test_context.ocr_service.ocr_matcher
    spy = MagicMock(wraps=matcher.ocr)
    monkeypatch.setattr(matcher, 'ocr', spy)
    assert tuple(read_loadout(test_context, screen).values()) == ('0', '0', '18000', '0/20', '0/5')
    assert spy.call_count > 0
    assert all(call.args[0].shape[1] < 1000 for call in spy.call_args_list)
