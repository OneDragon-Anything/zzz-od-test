"""插件导入后台线程与界面调度的回归测试。"""
import os
import threading
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from one_dragon.base.operation.application.plugin_import_service import ImportResult
from zzz_od.gui.view.setting import setting_plugin_interface as plugin_interface_module
from zzz_od.gui.view.setting.setting_plugin_interface import (
    PluginImportRunner,
    SettingPluginInterface,
)


def _ensure_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_plugin_import_runner_runs_task_in_background_thread() -> None:
    """导入任务应在后台线程执行，避免阻塞界面线程。"""
    app = _ensure_app()
    main_thread = threading.main_thread()
    task_threads: list[threading.Thread] = []

    def task() -> list[str]:
        task_threads.append(threading.current_thread())
        return ["done"]

    runner = PluginImportRunner(task)
    runner.start()
    assert runner.wait(5000)
    app.processEvents()

    assert task_threads
    assert task_threads[0] is not main_thread


def test_plugin_import_runner_delivers_results_to_main_thread() -> None:
    """导入结果应回到界面线程处理，便于弹窗与刷新。"""
    app = _ensure_app()
    main_thread = threading.main_thread()
    received: list[object] = []
    callback_threads: list[threading.Thread] = []

    def on_finished(results: object) -> None:
        received.append(results)
        callback_threads.append(threading.current_thread())

    runner = PluginImportRunner(lambda: ["first", "second"])
    runner.import_finished.connect(on_finished)
    runner.start()
    assert runner.wait(5000)
    app.processEvents()

    assert received == [["first", "second"]]
    assert callback_threads
    assert callback_threads[0] is main_thread


def test_plugin_import_runner_emits_failure_message() -> None:
    """导入任务出现未捕获异常时应发出失败信号。"""
    app = _ensure_app()
    failures: list[str] = []

    def task() -> list[str]:
        raise RuntimeError("模拟导入异常")

    runner = PluginImportRunner(task)
    runner.import_failed.connect(failures.append)
    runner.start()
    assert runner.wait(5000)
    app.processEvents()

    assert failures == ["模拟导入异常"]


class FakeInfoBar:
    """记录 InfoBar 调用的替身。"""

    calls: list[tuple[str, dict]] = []

    @classmethod
    def success(cls, **kwargs: object) -> None:
        cls.calls.append(("success", dict(kwargs)))

    @classmethod
    def error(cls, **kwargs: object) -> None:
        cls.calls.append(("error", dict(kwargs)))

    @classmethod
    def warning(cls, **kwargs: object) -> None:
        cls.calls.append(("warning", dict(kwargs)))


class StubButton:
    """带启用状态的按钮替身。"""

    def __init__(self) -> None:
        self.enabled: bool = True

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled


class StubCard:
    """带删除按钮的插件卡片替身。"""

    def __init__(self) -> None:
        self.delete_btn = StubButton()


class StubContext:
    """记录刷新次数的上下文替身。"""

    def __init__(self) -> None:
        self.refresh_count: int = 0

    def refresh_application_registration(self) -> None:
        self.refresh_count += 1


class StubHost(QObject):
    """承载导入调度方法的最小宿主。"""

    _start_plugin_import = SettingPluginInterface._start_plugin_import
    _cleanup_import_runner = SettingPluginInterface._cleanup_import_runner
    _on_plugin_import_failed = SettingPluginInterface._on_plugin_import_failed
    _set_import_operation_enabled = SettingPluginInterface._set_import_operation_enabled
    _finish_import_operation = SettingPluginInterface._finish_import_operation
    _wait_for_plugin_import = SettingPluginInterface._wait_for_plugin_import
    _finish_import_results = SettingPluginInterface._finish_import_results

    def __init__(self) -> None:
        super().__init__()
        self._import_runner = None
        self._import_busy = False
        self.import_btn = StubButton()
        self.import_dir_btn = StubButton()
        self.refresh_btn = StubButton()
        self._plugin_cards = [StubCard()]
        self.ctx = StubContext()
        self.refresh_calls: int = 0

    def _refresh_plugin_list(self) -> None:
        self.refresh_calls += 1


def _wait_for_import(host: StubHost, app: QApplication) -> None:
    """等待后台导入线程完成。"""
    deadline = time.monotonic() + 5
    while host._import_runner is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert host._import_runner is None, "后台导入未在超时前完成"


def test_start_plugin_import_restores_buttons_and_refreshes() -> None:
    """后台导入完成后应恢复按钮、刷新并展示结果。"""
    app = _ensure_app()
    FakeInfoBar.calls.clear()
    original_info_bar = plugin_interface_module.InfoBar
    plugin_interface_module.InfoBar = FakeInfoBar
    try:
        host = StubHost()
        host._set_import_operation_enabled(False)
        results = [ImportResult(success=True, plugin_name="demo", message="导入成功")]

        host._start_plugin_import(lambda: results, host._finish_import_results)
        _wait_for_import(host, app)
        app.processEvents()

        assert host.import_btn.enabled
        assert host.import_dir_btn.enabled
        assert host.refresh_btn.enabled
        assert host._plugin_cards[0].delete_btn.enabled
        assert host.ctx.refresh_count == 1
        assert host.refresh_calls == 1
        assert any(name == "success" for name, _ in FakeInfoBar.calls)
    finally:
        plugin_interface_module.InfoBar = original_info_bar


def test_start_plugin_import_reports_failure_and_restores_buttons() -> None:
    """后台导入任务异常时应提示并恢复按钮。"""
    app = _ensure_app()
    FakeInfoBar.calls.clear()
    original_info_bar = plugin_interface_module.InfoBar
    plugin_interface_module.InfoBar = FakeInfoBar
    try:
        host = StubHost()
        host._set_import_operation_enabled(False)

        def task() -> list[str]:
            raise RuntimeError("模拟导入异常")

        host._start_plugin_import(task, host._finish_import_results)
        _wait_for_import(host, app)
        app.processEvents()

        assert host.import_btn.enabled
        assert host.import_dir_btn.enabled
        assert host.refresh_btn.enabled
        assert host._plugin_cards[0].delete_btn.enabled
        assert host.ctx.refresh_count == 0
        assert any(name == "error" for name, _ in FakeInfoBar.calls)
    finally:
        plugin_interface_module.InfoBar = original_info_bar


def test_start_plugin_import_disables_refresh_and_delete_until_finished() -> None:
    """导入进行中应同时锁定刷新和插件删除。"""
    app = _ensure_app()
    started = threading.Event()
    release = threading.Event()

    def task() -> list[str]:
        started.set()
        assert release.wait(5)
        return ["done"]

    host = StubHost()
    host._start_plugin_import(task, host._finish_import_results)
    assert started.wait(5)

    assert not host.refresh_btn.enabled
    assert not host._plugin_cards[0].delete_btn.enabled

    release.set()
    _wait_for_import(host, app)
    app.processEvents()

    assert host.refresh_btn.enabled
    assert host._plugin_cards[0].delete_btn.enabled


def test_wait_for_plugin_import_waits_until_runner_finishes() -> None:
    """关闭界面时应等待后台导入线程结束。"""
    app = _ensure_app()
    release = threading.Event()

    def task() -> str:
        assert release.wait(5)
        return "done"

    host = StubHost()
    host._start_plugin_import(task, lambda _: None)
    waiter = threading.Thread(target=host._wait_for_plugin_import)
    waiter.start()
    time.sleep(0.05)

    assert waiter.is_alive()
    release.set()
    waiter.join(5)
    app.processEvents()

    assert not waiter.is_alive()
    assert host._import_runner is None
