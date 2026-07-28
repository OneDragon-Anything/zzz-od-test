"""LostVoidRunLevel.handle_interact 画面路由与入口过滤登记测试。"""
from unittest.mock import patch

import pytest
from test.conftest import TestContext

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_bangboo_store import (
    LostVoidBangbooStore,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import (
    LostVoidChooseCommon,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_gear import (
    LostVoidChooseGear,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_lottery import (
    LostVoidLottery,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_route_change import (
    LostVoidRouteChange,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidLevelInteractionState,
    LostVoidRunLevel,
)


def _make_op(test_context: TestContext) -> LostVoidRunLevel:
    """构造 handle_interact 所需的操作实例。"""
    return LostVoidRunLevel(
        test_context,
        LostVoidRegionType.ENTRY,
        LostVoidLevelInteractionState(),
    )


SUB_OP_CASES: list[tuple[str, type, str | None]] = [
    ('迷失之地-武备选择', LostVoidChooseGear, None),
    ('迷失之地-通用选择', LostVoidChooseCommon, None),
    ('迷失之地-邦布商店', LostVoidBangbooStore, '邦布商店'),
    ('迷失之地-路径迭换', LostVoidRouteChange, '路径迭换'),
    ('迷失之地-抽奖机', LostVoidLottery, '邦布商店'),  # TODO 抽奖机图标被误判成商店
]


@pytest.mark.parametrize(
    'screen_name, sub_op_cls, expected_interact_type',
    SUB_OP_CASES,
    ids=[case[0] for case in SUB_OP_CASES],
)
def test_handle_interact_routes_to_sub_op(
    test_context: TestContext,
    screen_name: str,
    sub_op_cls: type,
    expected_interact_type: str | None,
) -> None:
    """识别到子页面后执行对应操作，并登记需要过滤的入口类型。"""
    op = _make_op(test_context)
    mock_result = OperationResult(success=True, status='mocked')
    with (patch.object(op, 'check_and_update_current_screen', return_value=screen_name),
          patch.object(sub_op_cls, 'execute', return_value=mock_result) as mock_execute):
        result = op.handle_interact()

    assert mock_execute.called, f'{screen_name}: 应调用 {sub_op_cls.__name__}.execute'
    assert result.status == 'mocked', f'{screen_name}: 应透传子操作状态'
    expected_ignored_entry_name_set = (
        set() if expected_interact_type is None else {expected_interact_type}
    )
    assert op.level_interaction_state.ignored_entry_name_set == expected_ignored_entry_name_set


DIRECT_CASES: list[tuple[str, str]] = [
    ('迷失之地-挑战结果', '迷失之地-挑战结果'),
    ('迷失之地-大世界', '迷失之地-大世界'),
]


@pytest.mark.parametrize('screen_name, expected_status', DIRECT_CASES)
def test_handle_interact_direct_success(
    test_context: TestContext,
    screen_name: str,
    expected_status: str,
) -> None:
    """挑战结果和大世界画面直接返回对应状态。"""
    op = _make_op(test_context)
    with patch.object(op, 'check_and_update_current_screen', return_value=screen_name):
        result = op.handle_interact()

    assert result.is_success
    assert result.status == expected_status
