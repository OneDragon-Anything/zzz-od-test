from unittest.mock import MagicMock, patch

from one_dragon.base.operation.one_dragon_context import OneDragonContext


def test_run_record_refresh_failure_keeps_context_not_ready() -> None:
    """运行记录初始化失败时不能对外暴露为已就绪。"""
    ctx = MagicMock()
    ctx._init_lock.acquire.return_value = True
    ctx._application_registered = True
    ctx.custom_config.ui_language = 'zh_CN'
    ctx.env_config.is_debug = False
    ctx.current_instance_idx = 0
    ctx.run_context.check_and_update_all_run_record.side_effect = RuntimeError(
        'record broken'
    )

    with (
        patch(
            'one_dragon.base.operation.one_dragon_context.i18_utils.update_default_lang'
        ),
        patch(
            'one_dragon.base.operation.one_dragon_context.log_utils.set_log_level'
        ),
    ):
        OneDragonContext.init(ctx)

    assert ctx.ready_for_application is False
    ctx.push_service.init_push_channels.assert_not_called()
    ctx._init_lock.release.assert_called_once_with()
