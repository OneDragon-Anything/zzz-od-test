"""WPUSH 推送渠道测试。"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from one_dragon.base.push.channel.wpush import WPush
from test.conftest import TestContext
from test_push_channel_utils import create_test_image


class TestWPushHttpHandling:
    """HTTP 行为回归：代理、禁重定向、非 2xx 不解析 JSON。"""

    def setup_method(self) -> None:
        self.channel = WPush()
        self.config = {"APIKEY": "WPUSHtestkey", "CHANNEL": "wechat", "TOPIC_CODE": ""}

    def _mock_response(self, status_code: int, payload: dict) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        return resp

    @patch("one_dragon.base.push.channel.wpush.requests.post")
    def test_success_on_http_200_code_0(self, mock_post: MagicMock) -> None:
        mock_post.return_value = self._mock_response(200, {"code": 0, "message": "success"})
        proxy_url = "http://proxy.example:8080"
        expected_proxies = self.channel.get_proxy(proxy_url)

        ok, msg = self.channel.push(
            self.config,
            "t",
            "c",
            proxy_url=proxy_url,
        )

        assert ok
        assert "成功" in msg
        kwargs = mock_post.call_args.kwargs
        assert kwargs.get("allow_redirects") is False
        assert kwargs.get("proxies") == expected_proxies

    @patch("one_dragon.base.push.channel.wpush.requests.post")
    def test_reject_307_even_if_body_code_0(self, mock_post: MagicMock) -> None:
        response = self._mock_response(307, {"code": 0, "message": "redirect"})
        response.json.side_effect = AssertionError("non-2xx responses must not be parsed")
        mock_post.return_value = response

        ok, msg = self.channel.push(self.config, "t", "c")

        assert not ok
        assert "HTTP 307" in msg
        response.json.assert_not_called()

    @patch("one_dragon.base.push.channel.wpush.requests.post")
    def test_reject_308_even_if_body_code_0(self, mock_post: MagicMock) -> None:
        response = self._mock_response(308, {"code": 0, "message": "redirect"})
        response.json.side_effect = AssertionError("non-2xx responses must not be parsed")
        mock_post.return_value = response

        ok, msg = self.channel.push(self.config, "t", "c")

        assert not ok
        assert "HTTP 308" in msg
        response.json.assert_not_called()

    def test_validate_config_requires_apikey(self) -> None:
        ok, msg = self.channel.validate_config({"APIKEY": ""})
        assert not ok
        assert "APIKEY" in msg


class TestWPush:
    """真实 API 推送（需要 secrets）。"""

    @pytest.mark.requires_secrets
    def test_push(self, test_context: TestContext) -> None:
        channel_id = "WPUSH"

        push_config = test_context.push_service.push_config
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name="APIKEY",
            new_value=os.getenv("PUSH_WPUSH_APIKEY"),
        )
        push_config.update_channel_config_value(
            channel_id=channel_id,
            field_name="CHANNEL",
            new_value="wechat",
        )

        test_image = create_test_image(channel_id)
        result, message = test_context.push_service.push(
            channel_id=channel_id,
            content="这是一条测试推送消息\n\n包含测试标题和内容，验证推送功能是否正常工作。",
            image=test_image,
            title="测试推送通知",
        )

        assert result, f"推送测试失败: {message}"
