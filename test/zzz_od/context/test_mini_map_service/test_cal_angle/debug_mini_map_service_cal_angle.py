import os

from one_dragon.utils import cv2_utils, mini_map_angle_utils
from zzz_od.game_map.mini_map_wrapper import TOTAL_VIEW_ANGLE, RADIUS_RANGE
from zzz_od.context.zzz_context import ZContext


def __debug_cal_angle(debug_image_name: str, save: bool = False):
    ctx = ZContext()
    mini_map = cv2_utils.read_image(os.path.join(os.path.dirname(__file__), debug_image_name))
    mask = ctx.mini_map_service.get_view_mask(mini_map)
    _, results = mini_map_angle_utils.calculate(mask, view_angle=TOTAL_VIEW_ANGLE, radius_range=RADIUS_RANGE,
                                                debug_steps=True)
    from one_dragon.utils.mini_map_angle_visualizer import visualize_calculate
    visualize_calculate(mini_map, results)




if __name__ == '__main__':
    __debug_cal_angle('192_1.png')