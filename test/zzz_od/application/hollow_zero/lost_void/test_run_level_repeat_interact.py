"""LostVoidRunLevel 重复交互对象处理测试。"""
from types import SimpleNamespace
from unittest.mock import patch

from test.conftest import TestContext

import zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level as run_level_module
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_interact_target_const import (
    LostVoidInteractNPC,
    LostVoidInteractTarget,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidLevelInteractionState,
    LostVoidRunLevel,
)


def test_repeat_interact_moves_away_before_returning_to_detection(
    test_context: TestContext,
) -> None:
    """已完成的对象会先复用交互后移动逻辑离开，再返回非战斗识别。"""
    op = LostVoidRunLevel(
        test_context,
        LostVoidRegionType.FRIENDLY_TALK,
        LostVoidLevelInteractionState(),
    )
    op.last_screenshot = None
    target = LostVoidInteractTarget(
        name=LostVoidInteractNPC.MA_LIN.value,
        icon='感叹号',
        is_npc=True,
    )
    op.level_interaction_state.mark_completed(op.get_interact_target_key(target))

    with (patch.object(op, 'round_by_find_area', return_value=op.round_success()),
          patch.object(op, 'screenshot'),
          patch.object(op.ctx.screen_loader, 'get_area', return_value=SimpleNamespace(rect=None)),
          patch.object(op.ctx.ocr, 'crop_and_run_ocr', return_value={'玛琳': []}),
          patch.object(run_level_module, 'match_interact_target', return_value=target),
          patch.object(op, 'move_after_interact') as move_after_interact,
          patch.object(op.ctx.controller, 'interact') as interact,
          patch.object(run_level_module.time, 'sleep')):
        result = op.try_interact()

    assert not result.is_success
    assert result.status == '重复交互对象'
    assert op.interact_target is target
    move_after_interact.assert_called_once_with()
    interact.assert_not_called()
