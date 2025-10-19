import os

import pytest

from test.conftest import TestContext
from test_push_channel_utils import create_test_image


class TestTelegram:

    @pytest.mark.requires_secrets
    def test_push(self, test_context: TestContext):
        channel_id = 'TG'

        push_config = test_context.push_service.push_config
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='BOT_TOKEN',
            new_value=os.getenv('PUSH_TG_BOT_TOKEN', '')
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='USER_ID',
            new_value=os.getenv('PUSH_TG_USER_ID', '')
        )

        # 发送推送测试
        result, message = test_context.push_service.push(
            channel_id=channel_id,
            content='这是一条测试推送消息\n\n包含测试标题和内容，验证推送功能是否正常工作。后续不包含图片。',
            image=None,
            title='测试推送通知',
        )

        assert result, f"推送测试失败: {message}"

        # 创建测试图片
        test_image = create_test_image(channel_id)

        # 发送推送测试
        result, message = test_context.push_service.push(
            channel_id=channel_id,
            content='这是一条测试推送消息\n\n包含测试标题和内容，验证推送功能是否正常工作。后续包含图片。',
            image=test_image,
            title='测试推送通知',
        )

        assert result, f"推送测试失败: {message}"
