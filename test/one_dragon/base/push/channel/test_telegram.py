import os

from test.conftest import TestContext
from test_push_channel_utils import create_test_image


class TestPushPlus:

    def test_push(self, test_context: TestContext):
        channel_id = 'TG'

        # 配置钉钉机器人
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
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='PROXY_HOST',
            new_value=os.getenv('PUSH_PROXY_HOST', '')
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='PROXY_PORT',
            new_value=os.getenv('PUSH_PROXY_PORT', '')
        )

        # 创建测试图片
        test_image = create_test_image(channel_id)

        # 发送推送测试
        result, message = test_context.push_service.push(
            channel_id=channel_id,
            content='这是一条测试推送消息\n\n包含测试标题和内容，验证钉钉机器人的推送功能是否正常工作。',
            image=test_image,
            title='测试推送通知',
        )

        assert result, f"推送测试失败: {message}"
