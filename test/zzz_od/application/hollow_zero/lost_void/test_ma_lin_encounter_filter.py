"""玛琳交互后的偶遇事件入口过滤测试。"""
from types import SimpleNamespace

import pytest

import zzz_od.application.hollow_zero.lost_void.lost_void_app as lost_void_app_module
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.hollow_zero.lost_void.context.lost_void_context import (
    LostVoidContext,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_det_class import (
    LostVoidDetClass,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_app import LostVoidApp
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


class _FakeDetector:
    """仅记录 detect_to_go 实际下发的 YOLO 标签。"""

    def __init__(self) -> None:
        self.idx_2_class: dict[int, LostVoidDetClass] = {
            0: LostVoidDetClass(0, '0007-偶遇事件'),
            1: LostVoidDetClass(1, '0010-邦布商店'),
        }

    def run(self, screen: object, run_time: float, label_list: list[str] | None) -> list[str]:
        if label_list is None:
            return [det_class.class_name for det_class in self.idx_2_class.values()]
        return label_list


def _detect_entry_labels(state: LostVoidLevelInteractionState) -> list[str]:
    """通过真实 detect_to_go 标签筛选逻辑返回允许的 YOLO 标签。"""
    detector = _FakeDetector()
    lost_void_context = object.__new__(LostVoidContext)
    lost_void_context.detector = detector
    lost_void_context.ctx = SimpleNamespace(
        lost_void=SimpleNamespace(detector=detector),
    )
    return lost_void_context.detect_to_go(
        screen=None,
        screenshot_time=0,
        ignore_list=state.ignored_entry_name_list,
    )


def _run_level_with_status(
    app: LostVoidApp,
    status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> OperationResult:
    """直接运行 App 的状态处理分支，不执行真实层间移动。"""

    class FakeLostVoidRunLevel:
        STATUS_NEXT_LEVEL = LostVoidRunLevel.STATUS_NEXT_LEVEL
        STATUS_COMPLETE = LostVoidRunLevel.STATUS_COMPLETE

        def __init__(
            self,
            ctx: object,
            region_type: LostVoidRegionType,
            level_interaction_state: LostVoidLevelInteractionState,
        ) -> None:
            assert level_interaction_state is app.level_interaction_state

        def execute(self) -> OperationResult:
            return OperationResult(success=True, status=status)

    monkeypatch.setattr(lost_void_app_module, 'LostVoidRunLevel', FakeLostVoidRunLevel)
    return app.run_level()


def test_ma_lin_encounter_entry_is_filtered_until_next_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """玛琳完成后过滤偶遇；普通重进层间移动不清空，进入下一层才重置。"""
    state = LostVoidLevelInteractionState()
    op = object.__new__(LostVoidRunLevel)
    op.level_interaction_state = state
    op.locked_interact_target = LostVoidInteractTarget(
        name=LostVoidInteractNPC.MA_LIN.value,
        icon='感叹号',
        is_npc=True,
    )
    op.interact_target = LostVoidInteractTarget(
        name='未知',
        icon='感叹号',
        is_exclamation=True,
    )

    op.mark_locked_interact_completed()
    assert '0007-偶遇事件' not in _detect_entry_labels(state)
    assert '0010-邦布商店' in _detect_entry_labels(state)

    app = object.__new__(LostVoidApp)
    app.ctx = SimpleNamespace(
        lost_void=SimpleNamespace(had_interacted_ophelia_on_current_level=False),
    )
    app.next_region_type = LostVoidRegionType.ENTRY
    app.level_interaction_state = state
    app.round_by_op_result = lambda result: result

    _run_level_with_status(app, '非战斗区域', monkeypatch)
    assert '0007-偶遇事件' not in _detect_entry_labels(state)

    _run_level_with_status(app, LostVoidRunLevel.STATUS_NEXT_LEVEL, monkeypatch)
    assert '0007-偶遇事件' in _detect_entry_labels(state)
