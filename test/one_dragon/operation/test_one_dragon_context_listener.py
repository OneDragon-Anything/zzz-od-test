import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from one_dragon.base.conditional_operation.operation_executor import OperationExecutor
from one_dragon.base.conditional_operation.operator import ConditionalOperator
from one_dragon.base.conditional_operation.state_record_service import (
    StateRecordService,
)
from one_dragon.base.operation import one_dragon_context as context_module
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils import gpu_executor


@pytest.fixture
def context(monkeypatch: pytest.MonkeyPatch) -> OneDragonContext:
    """隔离模型、配置和系统输入，保留真实上下文生命周期。"""
    for name in (
        'ScreenContext', 'TemplateLoader', 'TemplateMatcher', 'DebugTraceBus',
        'OnnxOcrMatcher', 'OnnxOcrParam', 'OcrService', 'PcButtonListener',
        'ApplicationRunContext', 'ApplicationGroupManager', 'PushService',
    ):
        monkeypatch.setattr(context_module, name, MagicMock())
    monkeypatch.setattr(context_module.keyboard, 'Controller', MagicMock())
    monkeypatch.setattr(context_module.i18_utils, 'update_default_lang', MagicMock())
    monkeypatch.setattr(context_module.log_utils, 'set_log_level', MagicMock())

    ctx = OneDragonContext.__new__(OneDragonContext)
    ctx.__dict__.update(
        one_dragon_config=MagicMock(current_active_instance=SimpleNamespace(idx=1)),
        project_config=SimpleNamespace(screen_standard_width=1920, screen_standard_height=1080),
        model_config=SimpleNamespace(ocr_use_gpu=False),
        custom_config=SimpleNamespace(ui_language='zh'),
        env_config=SimpleNamespace(
            is_debug=False, is_gh_proxy=False,
            key_start_running='f9', key_stop_running='f10', key_screenshot='f11',
        ),
    )
    OneDragonContext.__init__(ctx)
    for name in (
        'register_application_factory', 'init_ocr', '_load_plugin_screens',
        'reload_instance_config', 'init_controller', 'init_for_application', 'init_others',
    ):
        monkeypatch.setattr(ctx, name, MagicMock())
    for cls in (
        context_module.ContextEventBus, context_module.OneDragonEnvContext,
        ConditionalOperator, OperationExecutor, StateRecordService, Application,
    ):
        monkeypatch.setattr(cls, 'after_app_shutdown', MagicMock())
    monkeypatch.setattr(gpu_executor, 'shutdown', MagicMock())
    return ctx


def test_constructor_does_not_start_listener(context: OneDragonContext) -> None:
    """构造阶段不安装全局输入监听。"""
    context.btn_listener.start.assert_not_called()
    assert not context.ready_for_application


def test_listener_starts_after_initialization(context: OneDragonContext) -> None:
    """最后的初始化完成且监听启动后，才允许执行应用。"""
    order = MagicMock()
    order.attach_mock(context.init_others, 'initialize')
    order.attach_mock(context.btn_listener.start, 'start')
    context.btn_listener.start.side_effect = lambda: (
        context.ready_for_application is False
        or pytest.fail('监听启动前已发布就绪状态')
    )

    context.init()

    assert order.mock_calls == [call.initialize(), call.start()]
    assert context.ready_for_application


@pytest.mark.parametrize('stage', ['init_ocr', 'init_for_application', 'init_others'])
def test_failed_initialization_does_not_start_listener(
    context: OneDragonContext, stage: str,
) -> None:
    """任一初始化阶段失败时，不启动监听或发布就绪状态。"""
    getattr(context, stage).side_effect = RuntimeError('初始化失败')

    context.init()

    context.btn_listener.start.assert_not_called()
    assert not context.ready_for_application


def test_reinitialization_starts_listener_once(context: OneDragonContext) -> None:
    """重复初始化不重复启动同一个线程。"""
    context.init()
    context.init()

    context.btn_listener.start.assert_called_once_with()
    assert context.ready_for_application


def test_shutdown_during_initialization_prevents_start(context: OneDragonContext) -> None:
    """初始化尚未完成就关闭时，后续不能启动监听。"""
    entered = threading.Event()
    resume = threading.Event()

    def wait_for_shutdown() -> None:
        entered.set()
        assert resume.wait(2)

    context.init_others.side_effect = wait_for_shutdown
    worker = threading.Thread(target=context.init)
    worker.start()
    try:
        assert entered.wait(2)
        assert not context.ready_for_application
        context.after_app_shutdown()
    finally:
        resume.set()
        worker.join(2)

    assert not worker.is_alive()
    context.btn_listener.start.assert_not_called()
    context.btn_listener.stop.assert_called_once_with()
    assert not context.ready_for_application


def test_shutdown_waits_for_listener_start(context: OneDragonContext) -> None:
    """关闭不能在监听启动尚未返回时停止同一监听。"""
    entered = threading.Event()
    resume = threading.Event()
    stopped = threading.Event()
    order: list[str] = []

    def start_listener() -> None:
        order.append('start')
        entered.set()
        assert resume.wait(2)
        order.append('started')

    def stop_listener() -> None:
        order.append('stop')
        stopped.set()

    context.btn_listener.start.side_effect = start_listener
    context.btn_listener.stop.side_effect = stop_listener
    initializer = threading.Thread(target=context.init)
    closer = threading.Thread(target=context.after_app_shutdown)
    initializer.start()
    try:
        assert entered.wait(2)
        closer.start()
        assert not stopped.wait(0.1)
    finally:
        resume.set()
        initializer.join(2)
        if closer.ident is not None:
            closer.join(2)

    assert not initializer.is_alive()
    assert not closer.is_alive()
    assert order == ['start', 'started', 'stop']
    assert not context.ready_for_application


@pytest.mark.parametrize(
    ('key', 'method'),
    [('f9', 'switch_context_pause_and_run'), ('f10', 'stop_running')],
)
def test_hotkeys_remain_available_after_initialization(
    context: OneDragonContext, key: str, method: str,
) -> None:
    """初始化后的暂停和停止快捷键仍走原有处理流程。"""
    context.init()

    context._on_key_press(key)

    getattr(context.run_context, method).assert_called_once_with()
