import os

import test
from one_dragon.utils import cv2_utils
from zzz_od.context.mini_map_service import MiniMapService


class TestMiniMapService(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_cal_angle(self):
        dir_path = self.sub_package_path
        for file_name in os.listdir(dir_path):
            if not file_name.endswith('.png'):
                continue

            mini_map = cv2_utils.read_image(os.path.join(dir_path, file_name))
            target_angle = file_name.split('_')[0]
            angle = MiniMapService.cal_angle(mini_map)
            print(f'{file_name} {angle}')

            angle_diff = abs(float(target_angle) - angle)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            self.assertTrue(angle_diff <= 10)


