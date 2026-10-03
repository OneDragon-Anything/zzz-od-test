from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

import pytest

from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from zzz_od.application.bagel.bagel_screen import read_loadout, zero_loadout

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('full_texts,crop_texts,expected', [
    (['装备', '0'], None, '0'),
    (['装备', '1000'], None, '1000'),
    (['0'], ['0'], '0'),
    (['装备0'], ['装备', '0'], '0'),
    (['装备'], ['装备', '@0'], '0'),
    (['装备'], ['装备', '@1000'], '1000'),
    (['装备', '0', '0'], ['装备', '0'], '0'),
    (['装备', '0', '@500'], None, ''),
    (['装备', '0', '500元'], None, ''),
    (['装备'], ['装备', '0', '@500'], ''),
    (['装备'], ['装备', '0', '1,000'], ''),
    (['装备', '0', '500'], ['装备', '0'], ''),
    (['@500'], ['装备', '@0'], ''),
    ([], [], ''),
    (['装备'], ['装备'], ''),
    (['装备'], ['装备', '0', '0'], ''),
    (['装备'], ['装备', '1000', '0'], ''),
    (['装备'], ['装备', '@0', '#0'], ''),
    (['装备'], ['装备', '@@@0'], ''),
    (['装备'], ['O'], ''),
])
def test_read_loadout_full_screen_then_crop(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    full_texts: list[str], crop_texts: list[str] | None, expected: str,
) -> None:
    """整屏须有标题和唯一数字，失败才裁完整标题条；无法确认不得当零。"""
    screen = test_context.load_screen('贝果-备战', '高危零携带-原生1080')
    area_names = ('武备价值', '装备价值', '道具价值', '背包数量', '安全箱数量')
    areas = [test_context.screen_loader.get_area('贝果-备战', name) for name in area_names]
    results = [['代理人武备', '0'], full_texts]
    expected_calls = [
        call(screen, rect=area.pc_rect, crop_first=False) for area in areas[:2]
    ]
    if crop_texts is not None:
        results.append(crop_texts)
        expected_calls.append(call(screen, rect=areas[1].pc_rect, crop_first=True))
    results.extend([['道具', '0'], ['0/20'], ['0/5']])
    expected_calls.append(call(screen, rect=areas[2].pc_rect, crop_first=False))
    expected_calls.extend(
        call(screen, rect=area.pc_rect, crop_first=True, color_range=area.color_range)
        for area in areas[3:]
    )
    ocr = MagicMock(side_effect=[
        [OcrMatchResult(1, 0, 0, 10, 10, data=text) for text in parts]
        for parts in results
    ])
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', ocr)

    values = read_loadout(test_context, screen)

    assert values == {
        '武备价值': '0', '装备价值': expected, '道具价值': '0',
        '背包数量': '0/20', '安全箱数量': '0/5',
    }
    assert zero_loadout(values) is (expected == '0')
    assert ocr.call_args_list == expected_calls
