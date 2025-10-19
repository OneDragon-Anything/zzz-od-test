import os

from test.conftest import TestContext
from test_push_channel_utils import create_test_image


class TestWebhook:

    def test_feishu(self, test_context: TestContext):
        channel_id = 'WEBHOOK'

        push_config = test_context.push_service.push_config
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='URL',
            new_value=os.getenv('PUSH_WEBHOOK_FS_URL')
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='METHOD',
            new_value="POST",  # 固定值
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='CONTENT_TYPE',
            new_value="application/json",  # 固定值
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='BODY',
            new_value='{ "msg_type": "text", "content": { "text": "$title\\n$content" } }',  # 固定值
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

    def test_discord(self, test_context: TestContext):
        channel_id = 'WEBHOOK'

        push_config = test_context.push_service.push_config
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='URL',
            new_value=os.getenv('PUSH_WEBHOOK_DISCORD_URL')
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='METHOD',
            new_value="POST",  # 固定值
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='CONTENT_TYPE',
            new_value="application/json",  # 固定值
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name='BODY',
            new_value='{ "content": "$content" }',  # 固定值
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