from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_slots import SAFE_SLOT_CENTERS

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.geometry.point import Point


def native_four_slot_screen() -> MatLike:
    """读取 PR 提供的原生四格局内画面，不修改原图。"""
    path = Path(__file__).resolve().parents[2] / 'screens/贝果-局内/四格安全箱部分占用-20261004.webp'
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
    for center in centers[capacity:]:
        copy_safe_slot(result, native, SAFE_SLOT_CENTERS[4], center)
    return result
