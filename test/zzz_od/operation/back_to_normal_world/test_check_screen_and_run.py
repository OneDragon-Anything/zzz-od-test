"""通用返回不得点击贝果标题，保留原有合法入口。"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.geometry.point import Point
from zzz_od.operation.back_to_normal_world import BackToNormalWorld

if TYPE_CHECKING:
    from test.conftest import TestContext


@pytest.mark.parametrize('text,accepted', [('迷宫诡域', False), ('域', False), ('区', False), ('街区', True), ('勘域', True), ('区域', True)])
def test_full_return_label(test_context: TestContext, monkeypatch: pytest.MonkeyPatch, text: str, accepted: bool) -> None:
    """只替换 OCR 输出，执行真实分支，非法词须转入返回箭头处理。"""
    op = BackToNormalWorld(test_context)
    monkeypatch.setattr(op, 'check_and_update_current_screen', lambda: None)
    monkeypatch.setattr(op, 'round_by_goto_screen', lambda **kwargs: op.round_fail())
    monkeypatch.setattr(test_context.world_patrol_service, 'cut_mini_map', lambda screen: MagicMock(play_mask_found=False))
    match = MagicMock(data=text, center=Point(310, 50))
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kwargs: [match])
    # 旧实现的 find_and_click_area 同样走真实 OCR 匹配；其余判据不需要图片。
    original = op.round_by_find_and_click_area
    monkeypatch.setattr(op, 'round_by_find_and_click_area', lambda screen, name, area: original(screen, name, area) if area == '左上角-区域' else op.round_success(area) if area == '返回' else op.round_retry())
    click = MagicMock(return_value=True)
    monkeypatch.setattr(test_context.controller, 'click', click)
    result = op.check_screen_and_run()
    assert result.status == ('左上角-区域' if accepted else '返回')
    assert click.call_count == int(accepted)
