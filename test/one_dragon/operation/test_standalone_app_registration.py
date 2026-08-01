from unittest.mock import MagicMock

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
)


def test_registry_application_only_exposes_default_or_standalone_apps() -> None:
    """应用运行只显示默认组和显式声明 STANDALONE 的应用。"""
    run_context = ApplicationRunContext(MagicMock())
    default_factory = MagicMock(app_id='default_app', standalone=False)
    standalone_factory = MagicMock(app_id='standalone_app', standalone=True)
    internal_factory = MagicMock(app_id='internal_app', standalone=False)

    run_context.registry_application(default_factory, default_group=True)
    run_context.registry_application(standalone_factory, default_group=False)
    run_context.registry_application(internal_factory, default_group=False)

    assert run_context.default_group_apps == ['default_app']
    assert run_context.standalone_app_ids == ['default_app', 'standalone_app']

    run_context.clear_applications()

    assert run_context.standalone_app_ids == []
