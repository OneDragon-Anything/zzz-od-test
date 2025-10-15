import os
import time
from typing import Optional

import pytest
from cv2.typing import MatLike

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.geometry.point import Point
from one_dragon.utils import cv2_utils
from zzz_od.config.game_config import GameConfig
from zzz_od.context.zzz_context import ZContext


class MockController(ControllerBase):

    def __init__(self, game_config: GameConfig,
                 standard_width: int = 1920,
                 standard_height: int = 1080):
        ControllerBase.__init__(self)
        self.game_config: GameConfig = game_config
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.mock_screenshot: MatLike = None

    def click(self, pos: Point = None, press_time: float = 0, pc_alt: bool = False) -> bool:
        if pos is None:
            return True
        return 0 <= pos.x < self.standard_width and 0 <= pos.y < self.standard_height

    def screenshot(self, independent: bool = False) -> tuple[float, MatLike]:
        return time.time(), self.mock_screenshot

    def dodge(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def switch_next(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def switch_prev(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def normal_attack(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def special_attack(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def ultimate(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def chain_left(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def chain_right(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def move_w(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def move_s(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def move_a(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def move_d(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def interact(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def turn_by_distance(self, d: float):
        pass

    def lock(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass

    def chain_cancel(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        pass


class TestContext(ZContext):
    def __init__(self):
        ZContext.__init__(self)

        self.controller: MockController | None = None

    def get_test_image(self, file_name: str, check_image_exist: bool = True) -> MatLike:
        """
        在调用者所在文件的目录 获取对应的图片

        Args:
            file_name: 图片名称 包含后缀
            check_image_exist: 是否检查图片是否存在

        Returns:
            MatLike: 图片 RGB格式
        """
        import inspect
        # 获取当前帧
        current_frame = inspect.currentframe()
        # 获取调用者的帧
        caller_frame = current_frame.f_back
        # 调用文件所在目录
        img_dir = os.path.dirname(caller_frame.f_code.co_filename)
        img_path = os.path.join(img_dir, file_name)
        if check_image_exist:
            assert os.path.exists(img_path), f'图片不存在: {img_path}'
        return cv2_utils.read_image(img_path)

    def add_mock_screenshot_by_path(self, file_name: str, check_image_exist: bool = True) -> None:
        """
        在调用者所在文件的目录 获取对应的图片 并设置到 controller 作为下一次 screenshot() 中获取到的截图

        Args:
            file_name: 图片名称 包含后缀
            check_image_exist: 是否检查图片是否存在
        """
        import inspect
        # 获取当前帧
        current_frame = inspect.currentframe()
        # 获取调用者的帧
        caller_frame = current_frame.f_back
        # 调用文件所在目录
        img_dir = os.path.dirname(caller_frame.f_code.co_filename)
        img_path = os.path.join(img_dir, file_name)
        if check_image_exist:
            assert os.path.exists(img_path), f'图片不存在: {img_path}'
        self.controller.mock_screenshot = cv2_utils.read_image(img_path)

    def add_mock_screenshot(self, screen: MatLike) -> None:
        """
        设置图片到 controller 作为下一次 screenshot() 中获取到的截图

        Args:
            screen: 图片
        """
        assert screen is not None and isinstance(screen, MatLike)
        self.controller.mock_screenshot = screen


@pytest.fixture(scope='session')
def test_context() -> TestContext:
    """创建模拟状态记录器"""
    ctx = TestContext()

    ctx.env_config.is_debug = True
    ctx.current_instance_idx = 99  # 使用特定的实例id
    ctx.init()
    ctx.controller = MockController(
        game_config=ctx.game_config,
        standard_width=ctx.project_config.screen_standard_width,
        standard_height=ctx.project_config.screen_standard_height,
    )

    return ctx
