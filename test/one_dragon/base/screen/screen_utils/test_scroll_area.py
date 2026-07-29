from types import SimpleNamespace

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_area import ScreenArea


class ScrollRecorder:

    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int]] = []

    def scroll(self, down: int, pos: Point | None = None) -> None:
        assert pos is not None
        self.calls.append((down, pos.x, pos.y))


def test_scroll_area_uses_wheel_direction_and_area_center() -> None:
    controller = ScrollRecorder()
    ctx = SimpleNamespace(controller=controller)
    area = ScreenArea(pc_rect=Rect(100, 200, 500, 600))

    screen_utils.scroll_area(ctx, area)
    screen_utils.scroll_area(ctx, area, direction='up')

    assert controller.calls == [
        (300, 300, 400),
        (-300, 300, 400),
    ]
