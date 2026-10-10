"""暂停期间不应累计为持续前进卡位。"""

from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow


@pytest.mark.usefixtures('no_round_wait')
def test_pause_resets_stall_before_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    """恢复首帧位置没变时，应重新校准，不能在移动前误报卡位。"""
    ctx = MagicMock(current_instance_idx=99)
    flow = load_published_flow('janus_high_a')
    step = flow.steps[8]
    assert step.action == 'move' and step.target is None
    op = BagelRunFlow(ctx, flow).build_operation(step)
    assert isinstance(op, BagelNavigate) and op.coordinate_only
    op.handle_init()
    op._cruise_progress = ((180.3, 89.9), 100.0)
    op.last_position = (180.3, 89.9)
    op.heading_aligned = True
    op.handle_pause()
    op.last_screenshot_time = 110.0
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, 'round_by_find_area', lambda _s, _page, area: op.round_success() if area == '按键-普通攻击' else op.round_fail())
    monkeypatch.setattr(op, 'minimap', lambda: None)
    monkeypatch.setattr(op.vision, 'locate', lambda _crop: (180.3, 89.9))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _crop: 72.5)
    result = op.move_to_target()
    assert not result.is_fail, result.status
    assert result.status == '短按W后等待箭头对齐'
    ctx.controller.move_w.assert_called_once()
