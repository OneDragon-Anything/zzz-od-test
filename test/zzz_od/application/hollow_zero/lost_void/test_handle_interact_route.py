"""LostVoidRunLevel.handle_interact 画面路由测试。

按 testing methodology 动作一:``handle_interact`` 按 ``check_and_update_current_screen``
识别出的画面名,路由到不同子 op 或直接返回 round_success。本文件覆盖两类分支:

1. 子 op 分支(武备选择 / 通用选择 / 邦布商店 / 路径迭换 / 抽奖机):
   patch 子 op 类的 ``execute`` 返回固定成功结果 → 调 ``handle_interact`` →
   断言子 op 被调用、``had_been_list`` 是否按 interact_type 追加、``round_wait`` 透传 status。

2. 直接返回分支(挑战结果 / 大世界):
   无子 op,直接断言 ``round_success`` 的 status。

所有用例使用的 fixture 均已存在 → 全部 GREEN。

源码行为(已读 ``lost_void_run_level.py`` 的 ``handle_interact`` 确认):
- 武备选择 / 通用选择:``interact_type`` 保持 ``None``,子 op 成功后不追加 ``had_been_list``。
- 邦布商店 / 路径迭换:``interact_type`` 分别为 ``邦布商店`` / ``路径迭换``,成功后追加。
- 抽奖机:``interact_type`` 被设为 ``邦布商店``(源码 TODO:1.6 新增的抽奖机图标会被误判成
  商店,等待后续模型更新),成功后同样追加 ``邦布商店``。
- 挑战结果 → ``round_success('迷失之地-挑战结果')``;大世界 → ``round_success('迷失之地-大世界')``。
"""
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
    LostVoidRunLevel,
)


def _make_op(test_context: TestContext) -> LostVoidRunLevel:
    """构造一个 ``LostVoidRunLevel`` 实例(用 ENTRY 区域类型,handle_interact 不依赖它)。"""
    return LostVoidRunLevel(test_context, LostVoidRegionType.ENTRY)


# 子 op 分支:(画面名, fixture state, 子 op 类, 期望 append 到 had_been_list 的 interact_type 或 None)
# 5 个 fixture 均已有 → GREEN。
SUB_OP_CASES: list[tuple[str, str, type, str | None]] = [
    ('迷失之地-武备选择', '初始战术棱镜方案', LostVoidChooseGear, None),
    ('迷失之地-通用选择', '选1张卡牌', LostVoidChooseCommon, None),
    ('迷失之地-邦布商店', '商店', LostVoidBangbooStore, '邦布商店'),
    ('迷失之地-路径迭换', '选定位卡', LostVoidRouteChange, '路径迭换'),
    ('迷失之地-抽奖机', '抽奖前', LostVoidLottery, '邦布商店'),  # TODO 抽奖机图标被误判为商店
]


@pytest.mark.parametrize(
    'screen_name, state, sub_op_cls, expected_interact_type', SUB_OP_CASES,
    ids=[c[1] for c in SUB_OP_CASES],
)
def test_handle_interact_routes_to_sub_op(
    test_context: TestContext, screen_name: str, state: str,
    sub_op_cls: type, expected_interact_type: str | None,
) -> None:
    """画面命中 → 实例化对应子 op 并 execute;成功后按 interact_type 决定是否追加 had_been_list。"""
    op = _make_op(test_context)
    test_context.mock_screen(screen_name, state)
    op.screenshot()

    mock_result = OperationResult(success=True, status='mocked')
    with patch.object(sub_op_cls, 'execute', return_value=mock_result) as mock_execute:
        result = op.handle_interact()

    # 子 op.execute 被路由调用
    assert mock_execute.called, f'{state}: 应调用 {sub_op_cls.__name__}.execute'
    # 子 op 成功后,handle_interact 返回 round_wait 并透传子 op status
    assert result.status == 'mocked', f'{state}: 应透传子 op status'
    # interact_type 非 None 时追加 had_been_list;为 None 时不追加
    if expected_interact_type is None:
        assert op.had_been_list == [], f'{state}: interact_type 为 None 不应追加 had_been_list'
    else:
        assert op.had_been_list == [expected_interact_type], (
            f'{state}: had_been_list 应追加 {expected_interact_type}'
        )


# 直接返回分支:(画面名, fixture state, 期望 round_success 的 status)
# 4 个 fixture 均已有 → GREEN。
DIRECT_CASES: list[tuple[str, str, str]] = [
    ('迷失之地-挑战结果', '奖励展示态', '迷失之地-挑战结果'),
    ('迷失之地-挑战结果', '完成态', '迷失之地-挑战结果'),
    ('迷失之地-挑战结果', '确定态', '迷失之地-挑战结果'),
    ('迷失之地-大世界', '玛琳前-以太稳定', '迷失之地-大世界'),
]


@pytest.mark.parametrize(
    'screen_name, state, expected_status', DIRECT_CASES,
    ids=[c[1] for c in DIRECT_CASES],
)
def test_handle_interact_direct_success(
    test_context: TestContext, screen_name: str, state: str, expected_status: str,
) -> None:
    """挑战结果 / 大世界分支无子 op,直接 round_success 返回固定 status。"""
    op = _make_op(test_context)
    test_context.mock_screen(screen_name, state)
    op.screenshot()

    result = op.handle_interact()

    assert result.is_success, f'{state}: 应返回 round_success'
    assert result.status == expected_status, f'{state}: status 应为 {expected_status}'
