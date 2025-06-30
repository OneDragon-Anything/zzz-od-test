import logging
import sys

import os
import unittest
from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.geometry.point import Point
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log, set_log_level
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

    def screenshot(self, independent: bool = False) -> MatLike:
        return self.mock_screenshot

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


class ZzzTestBase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        在每个测试方法运行前执行初始化
        """
        self.ctx = ZContext()
        self.ctx.env_config.is_debug = True
        self.ctx.init_by_config()
        self.ctx.current_instance_idx = 99  # 使用特定的实例id
        self.ctx.load_instance_config()
        self.ctx.init_ocr()
        self.ctx.controller = MockController(self.ctx.game_config,
                                             self.ctx.project_config.screen_standard_width,
                                             self.ctx.project_config.screen_standard_height)
        for handler in log.handlers:
            handler.setLevel(logging.WARN)

        # 获取子类的模块
        subclass_module = self.__class__.__module__
        subclass_file = sys.modules[subclass_module].__file__
        # 获取子类的路径
        sub_file_path = os.path.abspath(subclass_file)
        # 获取子类所在的包路径
        self.sub_package_path: str = os.path.dirname(sub_file_path)

        set_log_level(logging.DEBUG)

    def get_test_image(self, file_name: str) -> MatLike:
        """
        获取测试图片
        :param file_name: 文件名 包括后缀。使用全名方便在IDE中重命名文件时自动更改到对应代码
        :return:
        """
        if not file_name.endswith('.png'):
            file_name = f'{file_name}.png'
        img_path = os.path.join(self.sub_package_path, file_name)
        # self.assertTrue(os.path.exists(img_path), '图片不存在')
        return cv2_utils.read_image(img_path)

    def add_mock_screenshot(self, file_name: str) -> MatLike:
        """
        将图片放到controller中 方便op使用
        :param file_name: 同上
        :return:
        """
        screen = self.get_test_image(file_name)
        self.ctx.controller.mock_screenshot = screen
        return screen
