from pathlib import Path

from one_dragon.base.operation.application.plugin_info import PluginInfo, PluginSource
from zzz_od.gui.view.setting.setting_plugin_interface import SettingPluginInterface


class StubPluginImportService:
    def __init__(self, plugins_dir: Path) -> None:
        self.plugins_dir: Path = plugins_dir


class StubFactoryManager:
    def __init__(self, plugins: list[PluginInfo]) -> None:
        self._plugins_by_app_id = {plugin.app_id: plugin for plugin in plugins}

    def get_plugin_info(self, app_id: str) -> PluginInfo | None:
        return self._plugins_by_app_id.get(app_id)


class StubRunContext:
    def __init__(self, current_app_id: str | None, is_stopped: bool) -> None:
        self.current_app_id = current_app_id
        self.is_context_stop = is_stopped


class StubContext:
    def __init__(
        self,
        plugins: list[PluginInfo],
        current_app_id: str | None,
        is_stopped: bool,
    ) -> None:
        self.factory_manager = StubFactoryManager(plugins)
        self.run_context = StubRunContext(current_app_id, is_stopped)


class InterfaceMethods:
    _get_plugin_package_dir = SettingPluginInterface._get_plugin_package_dir
    _is_plugin_running = SettingPluginInterface._is_plugin_running

    def __init__(
        self,
        plugins_dir: Path,
        plugins: list[PluginInfo],
        current_app_id: str | None,
        is_stopped: bool,
    ) -> None:
        self.plugin_import_service = StubPluginImportService(plugins_dir)
        self.ctx = StubContext(plugins, current_app_id, is_stopped)


def test_delete_guard_rejects_running_plugin_package(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "demo"
    plugin = PluginInfo(
        app_id="demo_app",
        app_name="Demo",
        default_group=False,
        source=PluginSource.THIRD_PARTY,
        plugin_dir=plugin_dir,
    )
    interface = InterfaceMethods(plugins_dir, [plugin], "demo_app", False)

    assert interface._is_plugin_running(plugin_dir)


def test_delete_guard_allows_stopped_or_other_plugin(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    demo_dir = plugins_dir / "demo"
    other_dir = plugins_dir / "other"
    demo = PluginInfo(
        app_id="demo_app",
        app_name="Demo",
        default_group=False,
        source=PluginSource.THIRD_PARTY,
        plugin_dir=demo_dir,
    )
    other = PluginInfo(
        app_id="other_app",
        app_name="Other",
        default_group=False,
        source=PluginSource.THIRD_PARTY,
        plugin_dir=other_dir,
    )

    stopping = InterfaceMethods(plugins_dir, [demo], "demo_app", True)
    finished = InterfaceMethods(plugins_dir, [demo], None, True)
    running_other = InterfaceMethods(plugins_dir, [other], "other_app", False)

    assert stopping._is_plugin_running(demo_dir)
    assert not finished._is_plugin_running(demo_dir)
    assert not running_other._is_plugin_running(demo_dir)
