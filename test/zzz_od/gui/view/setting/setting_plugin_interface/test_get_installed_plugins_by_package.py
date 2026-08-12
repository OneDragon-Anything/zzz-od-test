from pathlib import Path

from one_dragon.base.operation.application.plugin_info import PluginInfo
from zzz_od.gui.view.setting.setting_plugin_interface import SettingPluginInterface


class StubPluginImportService:
    def __init__(self, plugins_dir: Path) -> None:
        self.plugins_dir: Path = plugins_dir


class StubFactoryManager:
    def __init__(self, plugins: list[PluginInfo]) -> None:
        self.third_party_plugins: list[PluginInfo] = plugins


class StubContext:
    def __init__(self, plugins: list[PluginInfo]) -> None:
        self.factory_manager: StubFactoryManager = StubFactoryManager(plugins)


class InterfaceMethods:
    _get_source_plugin_key = staticmethod(SettingPluginInterface._get_source_plugin_key)
    _get_plugin_package_dir = SettingPluginInterface._get_plugin_package_dir
    _get_installed_plugins_by_package = SettingPluginInterface._get_installed_plugins_by_package
    _is_version_lower = SettingPluginInterface._is_version_lower

    def __init__(self, plugins_dir: Path, plugins: list[PluginInfo]) -> None:
        self.plugin_import_service: StubPluginImportService = StubPluginImportService(plugins_dir)
        self.ctx: StubContext = StubContext(plugins)


def test_get_installed_plugins_by_package_uses_directory_name_and_shallowest_plugin(
    tmp_path: Path,
) -> None:
    plugins_dir = tmp_path / "plugins"
    package_dir = plugins_dir / "directory_name"
    root_plugin = PluginInfo(
        app_id="logical_app_id",
        app_name="Root",
        default_group=False,
        version="1.0.0",
        plugin_dir=package_dir,
    )
    nested_plugin = PluginInfo(
        app_id="nested_app_id",
        app_name="Nested",
        default_group=False,
        version="9.0.0",
        plugin_dir=package_dir / "features",
    )
    interface = InterfaceMethods(plugins_dir, [nested_plugin, root_plugin])

    installed = interface._get_installed_plugins_by_package()

    assert installed == {"directory_name": root_plugin}
    assert interface._get_plugin_package_dir(nested_plugin) == package_dir.resolve(strict=False)


def test_is_version_lower_uses_parsed_versions(tmp_path: Path) -> None:
    interface = InterfaceMethods(tmp_path / "plugins", [])

    assert interface._is_version_lower("8.0", "9.0")
    assert not interface._is_version_lower("10.0", "9.0")


def test_is_version_lower_does_not_compare_invalid_versions(tmp_path: Path) -> None:
    interface = InterfaceMethods(tmp_path / "plugins", [])

    assert not interface._is_version_lower("invalid", "9.0")
    assert not interface._is_version_lower("8.0", "invalid")


def test_source_plugin_key_uses_both_source_path_and_plugin_name(tmp_path: Path) -> None:
    first_source = tmp_path / "first.zip"
    second_source = tmp_path / "second.zip"

    first_plugin = InterfaceMethods._get_source_plugin_key(first_source, "plugin")
    second_plugin = InterfaceMethods._get_source_plugin_key(first_source, "other")
    other_source = InterfaceMethods._get_source_plugin_key(second_source, "plugin")

    assert first_plugin != second_plugin
    assert first_plugin != other_source
    assert first_plugin == InterfaceMethods._get_source_plugin_key(first_source, "PLUGIN")
