from pathlib import Path

from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)


def test_delete_plugin_rejects_root_outside_and_nested_paths(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    plugin_dir = plugin_import_service.plugins_dir / "plugin"
    nested_dir = plugin_dir / "nested"
    nested_dir.mkdir(parents=True)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    assert not plugin_import_service.delete_plugin(plugin_import_service.plugins_dir).success
    assert not plugin_import_service.delete_plugin(outside_dir).success
    assert not plugin_import_service.delete_plugin(nested_dir).success
    assert plugin_dir.exists()


def test_delete_plugin_rejects_top_level_file(
    plugin_import_service: PluginImportService,
) -> None:
    plugin_file = plugin_import_service.plugins_dir / "note.txt"
    plugin_file.parent.mkdir(parents=True)
    plugin_file.write_text("keep", encoding="utf-8")

    result = plugin_import_service.delete_plugin(plugin_file)

    assert not result.success
    assert plugin_file.read_text(encoding="utf-8") == "keep"


def test_delete_plugin_removes_top_level_plugin_directory(
    plugin_import_service: PluginImportService,
) -> None:
    plugin_dir = plugin_import_service.plugins_dir / "plugin"
    plugin_dir.mkdir(parents=True)

    result = plugin_import_service.delete_plugin(plugin_dir)

    assert result.success
    assert not plugin_dir.exists()
