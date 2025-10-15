import os

from test.conftest import TestContext

from one_dragon.utils import cv2_utils
from zzz_od.application.world_patrol.mini_map_wrapper import MiniMapWrapper


class TestMiniMapService:

    def test_cal_angle(self, test_context: TestContext):
        dir_path = os.path.dirname(__file__)
        for file_name in os.listdir(dir_path):
            if not file_name.endswith('.png'):
                continue

            mini_map = cv2_utils.read_image(os.path.join(dir_path, file_name))
            mini_map_wrapper = MiniMapWrapper(mini_map)
            target_angle = file_name.split('_')[0]
            angle = mini_map_wrapper.view_angle
            print(f'{file_name} {angle}')

            angle_diff = abs(float(target_angle) - angle)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            assert angle_diff <= 10