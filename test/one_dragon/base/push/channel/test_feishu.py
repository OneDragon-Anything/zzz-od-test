import os

import cv2
import numpy as np
from cv2.typing import MatLike

from test.conftest import TestContext


class TestFeishu:

    def _create_test_image(self) -> MatLike:
        """
        创建一张测试图片

        Returns:
            创建的测试图片
        """
        # 创建一个 200x100 的蓝色背景图片
        image = np.full((100, 200, 3), (255, 200, 100), dtype=np.uint8)  # BGR格式的浅蓝色

        # 在图片上绘制文字
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(image, 'Test Image', (20, 40), font, 0.8, (0, 0, 0), 2)  # 黑色文字
        cv2.putText(image, '2024-01-01', (20, 70), font, 0.6, (0, 0, 0), 2)  # 黑色文字

        # 绘制一些简单的图形
        cv2.circle(image, (170, 30), 15, (0, 255, 0), -1)  # 绿色实心圆
        cv2.rectangle(image, (10, 80), (40, 95), (0, 0, 255), 2)  # 红色矩形边框

        return image

    def test_push(self, test_context: TestContext):
        channel_id = 'FS'

        # 配置钉钉机器人
        push_config = test_context.push_service.push_config
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='CHANNEL',
            new_value='Lark'
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='KEY',
            new_value=os.getenv('PUSH_FS_KEY')
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='BOT_SECRET',
            new_value=os.getenv('PUSH_FS_BOT_SECRET')
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='APPID',
            new_value=os.getenv('PUSH_FS_APP_ID')
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='APPSECRET',
            new_value=os.getenv('PUSH_FS_APP_SECRET')
        )

        # 创建测试图片
        test_image = self._create_test_image()

        # 发送推送测试
        result, message = test_context.push_service.push(
            channel_id=channel_id,
            content='这是一条测试推送消息\n\n包含测试标题和内容，验证钉钉机器人的推送功能是否正常工作。',
            image=test_image,
            title='测试推送通知',
        )

        assert result, f"推送测试失败: {message}"
