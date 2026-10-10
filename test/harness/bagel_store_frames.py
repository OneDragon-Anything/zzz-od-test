from __future__ import annotations

from typing import TYPE_CHECKING

from test.harness.bagel_loadout import TransferController
from test.harness.fixture_controller import WatchdogOperationMixin
from zzz_od.application.bagel.bagel_store import BagelStoreSafe

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.geometry.point import Point
    from test.conftest import TestContext


def copy_result_item(
    screen: MatLike, source: MatLike, start: Point, end: Point
) -> None:
    """只合成图标底色和角标，保留结果面板自己的格框和行距。"""
    screen[end.y - 40 : end.y + 40, end.x - 40 : end.x + 40] = source[
        start.y - 40 : start.y + 40,
        start.x - 40 : start.x + 40,
    ]
    screen[end.y - 56 : end.y - 32, end.x - 46 : end.x - 22] = source[
        start.y - 56 : start.y - 32,
        start.x - 46 : start.x - 22,
    ]


class SafeDragController(TransferController):
    """用完整截图推进拖拽前后两帧，只记录输入。"""

    def __init__(self, ctx: TestContext) -> None:
        """记录目标格，验证没有操作锁定位置。"""
        super().__init__(ctx)
        self.drags: list[Point] = []

    def drag_to(
        self,
        end: Point,
        start: Point | None = None,
        duration: float = 0.5,
        press_time: float = 0,
    ) -> None:
        """只在拖拽阶段推进，额外拖拽会被最终断言捕获。"""
        self.drags.append(end)
        if self._current_exit() == ('on_drag',):
            self._advance_phase()


class WatchedSafeStore(WatchdogOperationMixin, BagelStoreSafe):
    """限制完整收集流程的轮数。"""

    watchdog_max_rounds: int = 20
