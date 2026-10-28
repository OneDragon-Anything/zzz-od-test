from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from one_dragon.base.screen.screen_loader import ScreenContext
from one_dragon.utils import cv2_utils
from one_dragon.yolo.detect_utils import (
    DetectClass,
    DetectFrameResult,
    DetectObjectResult,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import (
    LostVoidDetector,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation import lost_void_move_by_det
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    LostVoidMoveByDet,
)

if TYPE_CHECKING:
    from cv2.typing import MatLike


@pytest.fixture(scope='session')
def world_frame() -> MatLike:
    """读取已归档的挚交会谈场景，不初始化 OCR 或游戏窗口。"""
    test_root = next(parent for parent in Path(__file__).parents if (parent / 'screens').is_dir())
    return cv2_utils.read_image(str(test_root / 'screens/迷失之地-大世界/玛琳前-以太稳定.webp'))


@pytest.fixture(scope='session')
def blocked_animation_frames() -> list[MatLike]:
    """读取同一护栏卡点的大型角色两帧待机动画。"""
    test_root = next(parent for parent in Path(__file__).parents if (parent / 'screens').is_dir())
    return [
        cv2_utils.read_image(str(test_root / f'screens/迷失之地-大世界/护栏前-角色动画-{suffix}.webp'))
        for suffix in ['a', 'b']
    ]


@pytest.fixture(scope='session')
def takeoff_frame() -> MatLike:
    """读取用户反馈的护栏前起飞状态截图。"""
    test_root = next(parent for parent in Path(__file__).parents if (parent / 'screens').is_dir())
    return cv2_utils.read_image(str(test_root / 'screens/迷失之地-大世界/护栏前-起飞.webp'))


@pytest.fixture()
def moving_op(
    world_frame: MatLike,
    motion_screen_loader: ScreenContext,
    monkeypatch: pytest.MonkeyPatch,
) -> LostVoidMoveByDet:
    """构造只替换检测与输入的寻路操作，保留实际帧差和方向选择。"""
    ctx = MagicMock()
    ctx.controller.standard_width = 1920
    ctx.controller.standard_height = 1080
    ctx.project_config.screen_standard_width = 1920
    ctx.project_config.screen_standard_height = 1080
    ctx.run_context.get_config.return_value = SimpleNamespace(
        stuck_sample_interval=0.5,
        stuck_static_seconds=2.0,
        stuck_motion_threshold=0.03,
        stuck_escape_seconds=0.8,
        stuck_max_forward_seconds=8.0,
    )
    ctx.screen_loader = motion_screen_loader
    ctx.lost_void.in_normal_world.return_value = True
    ctx.lost_void.check_battle_encounter.return_value = False
    ctx.lost_void.check_battle_encounter_in_period.return_value = False
    ctx.lost_void.detector = object.__new__(LostVoidDetector)
    target = DetectObjectResult([940, 300, 980, 340], 1.0, DetectClass(0, LostVoidDetector.CLASS_INTERACT))
    ctx.lost_void.detect_to_go.return_value = DetectFrameResult(world_frame, [target])
    ctx.controller.screenshot.return_value = (100.0, world_frame)
    ctx.auto_battle_context.is_normal_attack_btn_available.return_value = True
    monkeypatch.setattr(lost_void_move_by_det.auto_battle_utils, 'switch_to_best_agent_for_moving', MagicMock())
    monkeypatch.setattr(lost_void_move_by_det, 'time', SimpleNamespace(time=lambda: 100.0, sleep=MagicMock()))
    op = LostVoidMoveByDet(ctx, LostVoidRegionType.ENTRY, LostVoidDetector.CLASS_INTERACT)
    op.last_screenshot = world_frame
    op.last_screenshot_time = 100.0
    monkeypatch.setattr(op, '_after_round_wait', MagicMock())

    def find_area(screen: MatLike, screen_name: str, area_name: str) -> OperationRoundResult:
        """默认只有普攻按钮，尚未到达交互距离。"""
        found = area_name == '按键-普通攻击'
        return OperationRoundResult(OperationRoundResultEnum.SUCCESS if found else OperationRoundResultEnum.RETRY)

    monkeypatch.setattr(op, 'round_by_find_area', find_area)
    return op


@pytest.fixture(scope='session')
def motion_screen_loader() -> ScreenContext:
    """按程序默认路径加载合并配置，防止只改单独 YAML 导致实机缺区域。"""
    loader = ScreenContext()
    loader.reload()
    return loader
