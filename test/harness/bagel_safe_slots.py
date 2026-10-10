from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import cv2

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.pc_screenshot_controller import (
    PcScreenshotController,
)
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.envs.env_config import ScreenshotMethodEnum
from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_slots import (
    SAFE_SLOT_CENTERS,
    WAREHOUSE_SAFE_CENTERS,
)

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.geometry.point import Point


def native_four_slot_screen() -> MatLike:
    """读取 PR 提供的原生四格局内画面，不修改原图。"""
    path = Path(__file__).resolve().parents[2] / 'screens/贝果-局内/四格安全箱部分占用-20261004.webp'
    return cv2_utils.read_image(str(path))


def warehouse_safe_screen(occupied: bool = False) -> MatLike:
    """读取同一录像的仓库入仓前后画面，保持仓库自身格子和背景。"""
    state = '带物资仓库-r07-117s' if occupied else '入仓后安全箱空-r07-118s'
    path = Path(__file__).resolve().parents[2] / f'screens/贝果-仓库/{state}.webp'
    return cv2_utils.read_image(str(path))


def copy_safe_slot(screen: MatLike, source: MatLike, start: Point, end: Point) -> None:
    """复制完整格子及角标；合成帧仅验证流程，不冒充实拍。"""
    screen[end.y - 58:end.y + 55, end.x - 49:end.x + 49] = source[
        start.y - 58:start.y + 55, start.x - 49:start.x + 49,
    ].copy()


def lock_safe_suffix(
    screen: MatLike, capacity: int, centers: tuple[Point, ...] = SAFE_SLOT_CENTERS,
) -> MatLike:
    """按用户确认的锁图标与 LOCK 规则，合成指定容量的未开放格。"""
    result = screen.copy()
    native = native_four_slot_screen()
    warehouse = centers == WAREHOUSE_SAFE_CENTERS
    empty = warehouse_safe_screen() if warehouse else None
    for center in centers[capacity:]:
        if warehouse:
            # 仓库保留自己的槽框；只移植锁图标与 LOCK，不能把局内整格贴进仓库。
            copy_safe_slot(result, empty, center, center)
            source = SAFE_SLOT_CENTERS[4]
            result[center.y - 48:center.y + 48, center.x - 40:center.x + 40] = native[
                source.y - 48:source.y + 48, source.x - 40:source.x + 40,
            ]
        else:
            copy_safe_slot(result, native, SAFE_SLOT_CENTERS[4], center)
    return result


def capacity_safe_screen(capacity: int, warehouse: bool = False) -> MatLike:
    """按各自实拍合成一件占用的小容量安全箱；仓库只合成未开放格内部。"""
    if warehouse:
        centers = WAREHOUSE_SAFE_CENTERS
        screen = warehouse_safe_screen()
        copy_safe_slot(screen, warehouse_safe_screen(occupied=True), centers[0], centers[0])
    else:
        centers = SAFE_SLOT_CENTERS
        native = native_four_slot_screen()
        screen = native.copy()
        for center in centers:
            copy_safe_slot(screen, native, centers[1], center)
        copy_safe_slot(screen, native, centers[0], centers[0])
    return lock_safe_suffix(screen, capacity, centers)


def capture_scaled_safe_screen(size: tuple[int, int]) -> tuple[MatLike, MatLike]:
    """模拟非 1080p 原始抓图，经过真实截图控制器的默认缩放路径。"""
    raw = cv2.resize(native_four_slot_screen(), size)
    game_win = MagicMock(spec=PcGameWindow)
    game_win.win_rect = Rect(0, 0, *size)
    game_win.is_win_scale = size != (1920, 1080)
    controller = PcScreenshotController(game_win, 1920, 1080)
    method = ScreenshotMethodEnum.PRINT_WINDOW.value.value
    controller.active_strategy_name = method
    strategy = MagicMock()
    strategy.capture.return_value = raw
    controller.strategies = {method: strategy}
    normalized = controller.get_screenshot()
    assert normalized is not None
    strategy.capture.assert_called_once()
    return raw, normalized
