from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginSource

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


def _record_factory_files(
    manager: ApplicationFactoryManager,
    monkeypatch: pytest.MonkeyPatch,
) -> list[Path]:
    loaded_files: list[Path] = []

    def record_load(
        factory_file: Path,
        reload_modules: bool = False,
        source: PluginSource = PluginSource.BUILTIN,
        base_dir: Path | None = None,
    ) -> tuple[ApplicationFactory, bool]:
        loaded_files.append(factory_file)
        return cast(ApplicationFactory, object()), False

    monkeypatch.setattr(manager, "_load_factory_from_file", record_load)
    return loaded_files


def test_third_party_scan_only_loads_factory_from_plugin_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "my_plugin"
    nested_dir = plugin_dir / "sub"
    nested_dir.mkdir(parents=True)
    root_factory = plugin_dir / "my_plugin_factory.py"
    root_factory.write_text("", encoding="utf-8")
    (plugin_dir / "my_plugin_const.py").write_text("", encoding="utf-8")
    (nested_dir / "nested_factory.py").write_text("", encoding="utf-8")
    (nested_dir / "other_factory.py").write_text("", encoding="utf-8")

    manager = ApplicationFactoryManager(cast("OneDragonContext", object()), [])
    loaded_files = _record_factory_files(manager, monkeypatch)

    manager._scan_directory(plugins_dir, source=PluginSource.THIRD_PARTY)

    assert loaded_files == [root_factory]
    assert manager.scan_failures == []


def test_third_party_scan_skips_symlink_plugin_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugins_dir = tmp_path / "plugins"
    outside_dir = tmp_path / "outside"
    plugins_dir.mkdir()
    outside_dir.mkdir()
    outside_factory = outside_dir / "outside_factory.py"
    outside_factory.write_text("", encoding="utf-8")
    (outside_dir / "outside_const.py").write_text("", encoding="utf-8")
    try:
        (plugins_dir / "linked_plugin").symlink_to(
            outside_dir,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("当前环境不允许创建目录符号链接")

    manager = ApplicationFactoryManager(cast("OneDragonContext", object()), [])
    loaded_files = _record_factory_files(manager, monkeypatch)

    manager._scan_directory(plugins_dir, source=PluginSource.THIRD_PARTY)

    assert loaded_files == []
    assert manager.scan_failures == []


def test_third_party_scan_skips_symlink_factory_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "plugins" / "safe_plugin"
    outside_dir = tmp_path / "outside"
    plugin_dir.mkdir(parents=True)
    outside_dir.mkdir()
    outside_factory = outside_dir / "outside_factory.py"
    outside_factory.write_text("", encoding="utf-8")
    (plugin_dir / "safe_plugin_const.py").write_text("", encoding="utf-8")
    try:
        (plugin_dir / "safe_plugin_factory.py").symlink_to(outside_factory)
    except OSError:
        pytest.skip("当前环境不允许创建文件符号链接")

    manager = ApplicationFactoryManager(cast("OneDragonContext", object()), [])
    loaded_files = _record_factory_files(manager, monkeypatch)

    manager._scan_directory(plugin_dir.parent, source=PluginSource.THIRD_PARTY)

    assert loaded_files == []
    assert manager.scan_failures == []


def test_builtin_scan_keeps_recursive_factory_discovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    application_dir = tmp_path / "application"
    first_factory = application_dir / "first" / "first_factory.py"
    nested_factory = application_dir / "group" / "second" / "second_factory.py"
    first_factory.parent.mkdir(parents=True)
    nested_factory.parent.mkdir(parents=True)
    first_factory.write_text("", encoding="utf-8")
    nested_factory.write_text("", encoding="utf-8")

    manager = ApplicationFactoryManager(cast("OneDragonContext", object()), [])
    loaded_files = _record_factory_files(manager, monkeypatch)

    manager._scan_directory(application_dir, source=PluginSource.BUILTIN)

    assert set(loaded_files) == {first_factory, nested_factory}
