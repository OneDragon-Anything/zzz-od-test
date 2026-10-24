from unittest import mock

import pytest

from one_dragon.base.matcher.ocr.onnx_ocr_matcher import (
    DEFAULT_OCR_MODEL_NAME,
    PPOCRV6_MODEL_NAME,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext


class TestOcrModelDecision:

    def _make_context(self, is_debug: bool, config_ocr: str) -> OneDragonContext:
        """
        构造一个轻量上下文 绕过重量级 __init__
        """
        ctx = OneDragonContext.__new__(OneDragonContext)
        ctx.env_config = mock.Mock()
        ctx.env_config.is_debug = is_debug
        ctx.model_config = mock.Mock()
        ctx.model_config.ocr = config_ocr
        ctx.model_config.update = lambda name, val: setattr(ctx.model_config, 'ocr', val)
        ctx._ocr_v6_downloading = False
        return ctx

    def test_debug_mode_uses_config(self):
        """
        调试模式: 直接用配置里的模型 不自动切换
        """
        ctx = self._make_context(is_debug=True, config_ocr=DEFAULT_OCR_MODEL_NAME)
        with mock.patch.object(
                OneDragonContext, '_is_ocr_model_ready',
                side_effect=lambda name: {PPOCRV6_MODEL_NAME: True, DEFAULT_OCR_MODEL_NAME: True}[name],
        ):
            assert ctx._decide_ocr_model_name() == DEFAULT_OCR_MODEL_NAME

    def test_v6_ready_uses_v6(self):
        """
        正常模式 仅 V6 就绪: 用 V6
        """
        ctx = self._make_context(is_debug=False, config_ocr=DEFAULT_OCR_MODEL_NAME)
        with mock.patch.object(
                OneDragonContext, '_is_ocr_model_ready',
                side_effect=lambda name: {PPOCRV6_MODEL_NAME: True, DEFAULT_OCR_MODEL_NAME: False}[name],
        ):
            assert ctx._decide_ocr_model_name() == PPOCRV6_MODEL_NAME

    def test_v5_ready_uses_v5(self):
        """
        正常模式 仅 V5 就绪: 先用 V5 顶住
        """
        ctx = self._make_context(is_debug=False, config_ocr=PPOCRV6_MODEL_NAME)
        with mock.patch.object(
                OneDragonContext, '_is_ocr_model_ready',
                side_effect=lambda name: {PPOCRV6_MODEL_NAME: False, DEFAULT_OCR_MODEL_NAME: True}[name],
        ):
            assert ctx._decide_ocr_model_name() == DEFAULT_OCR_MODEL_NAME

    def test_none_ready_uses_v6(self):
        """
        正常模式 都没有: 直接用 V6 触发下载
        """
        ctx = self._make_context(is_debug=False, config_ocr=DEFAULT_OCR_MODEL_NAME)
        with mock.patch.object(
                OneDragonContext, '_is_ocr_model_ready',
                side_effect=lambda name: {PPOCRV6_MODEL_NAME: False, DEFAULT_OCR_MODEL_NAME: False}[name],
        ):
            assert ctx._decide_ocr_model_name() == PPOCRV6_MODEL_NAME


class TestOcrV6BackgroundDownload:

    def _make_context(self) -> OneDragonContext:
        """
        构造一个轻量上下文
        """
        ctx = OneDragonContext.__new__(OneDragonContext)
        ctx.env_config = mock.Mock()
        ctx.env_config.is_debug = False
        ctx.env_config.is_gh_proxy = False
        ctx.env_config.gh_proxy_url = ''
        ctx.env_config.is_personal_proxy = False
        ctx.env_config.personal_proxy = ''
        ctx.model_config = mock.Mock()
        ctx.model_config.ocr = DEFAULT_OCR_MODEL_NAME
        ctx.model_config.update = lambda name, val: setattr(ctx.model_config, 'ocr', val)
        ctx._ocr_v6_downloading = False
        return ctx

    def _run_download_task(self, ctx: OneDragonContext, download_result) -> mock.Mock:
        """
        同步执行后台下载逻辑 返回 init_ocr 的 mock
        """
        fake_matcher = mock.Mock()
        fake_matcher.download = mock.Mock(return_value=download_result)

        with mock.patch(
                'one_dragon.base.operation.one_dragon_context.OnnxOcrMatcher',
                return_value=fake_matcher,
        ):
            with mock.patch(
                    'one_dragon.base.operation.one_dragon_context.threading.Thread',
            ) as mock_thread:
                with mock.patch.object(OneDragonContext, 'init_ocr') as mock_init:
                    # 让 start 同步执行线程目标
                    def sync_start():
                        target = mock_thread.call_args.kwargs['target']
                        target()

                    mock_thread.return_value.start = sync_start
                    ctx._download_ocr_v6_in_background()
                    return mock_init

    def test_download_success_only_persists_config(self):
        """
        下载成功: 只落盘配置 不立刻切换 下次启动生效
        """
        ctx = self._make_context()
        mock_init = self._run_download_task(ctx, download_result=True)

        # 落盘配置为 v6
        assert ctx.model_config.ocr == PPOCRV6_MODEL_NAME
        # 不立刻切换
        mock_init.assert_not_called()

    def test_download_failure_keeps_v5(self):
        """
        下载失败: 不落盘 保持 V5 配置
        """
        ctx = self._make_context()
        self._run_download_task(ctx, download_result=False)

        assert ctx.model_config.ocr == DEFAULT_OCR_MODEL_NAME

    def test_download_exception_keeps_v5(self):
        """
        下载异常: 不落盘 保持 V5 配置 状态复位
        """
        ctx = self._make_context()

        fake_matcher = mock.Mock()
        fake_matcher.download = mock.Mock(side_effect=RuntimeError('网络异常'))

        with mock.patch(
                'one_dragon.base.operation.one_dragon_context.OnnxOcrMatcher',
                return_value=fake_matcher,
        ):
            with mock.patch(
                    'one_dragon.base.operation.one_dragon_context.threading.Thread',
            ) as mock_thread:
                def sync_start():
                    target = mock_thread.call_args.kwargs['target']
                    target()

                mock_thread.return_value.start = sync_start
                ctx._download_ocr_v6_in_background()

        assert ctx.model_config.ocr == DEFAULT_OCR_MODEL_NAME
        # 状态复位 下次可重试
        assert ctx._ocr_v6_downloading is False

    def test_no_duplicate_download(self):
        """
        下载进行中 不重复启动
        """
        ctx = self._make_context()
        ctx._ocr_v6_downloading = True
        with mock.patch(
                'one_dragon.base.operation.one_dragon_context.OnnxOcrMatcher',
        ) as mock_matcher:
            ctx._download_ocr_v6_in_background()
            mock_matcher.assert_not_called()


if __name__ == '__main__':
    pytest.main(['-v', __file__])
