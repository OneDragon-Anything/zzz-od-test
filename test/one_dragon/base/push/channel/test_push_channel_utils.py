import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.utils import os_utils


def create_test_image(channel_id: str) -> MatLike:
    """
    创建一张测试图片

    Args:
        channel_id: 推送渠道ID

    Returns:
        创建的测试图片
    """
    # 创建一个 200x100 的蓝色背景图片
    image = np.full((100, 200, 3), (255, 200, 100), dtype=np.uint8)  # BGR格式的浅蓝色

    # 在图片上绘制文字
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(image, channel_id, (20, 40), font, 0.8, (0, 0, 0), 2)  # 黑色文字
    cv2.putText(image, os_utils.get_dt(8), (20, 70), font, 0.6, (0, 0, 0), 2)  # 黑色文字

    # 绘制一些简单的图形
    cv2.circle(image, (170, 30), 15, (0, 255, 0), -1)  # 绿色实心圆
    cv2.rectangle(image, (10, 80), (40, 95), (0, 0, 255), 2)  # 红色矩形边框

    return image