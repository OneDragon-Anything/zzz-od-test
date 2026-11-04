import json
from collections.abc import Callable
from pathlib import Path

from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)


def test_preview_plugin_reads_primary_const_from_wrapped_plugin_root(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "preview.zip"
    create_zip(
        zip_path,
        {
            "repository-main/README.md": "不属于插件",
            "repository-main/package/package_factory.py": "",
            "repository-main/package/package_const.py": "",
            "repository-main/package/plugin.json": json.dumps(
                {"version": "3.2.1", "author": {"name": "tester"}}
            ),
            "repository-main/package/features/feature_factory.py": "",
            "__MACOSX/._feature": "",
        },
    )

    preview = plugin_import_service.preview_plugin(zip_path)

    assert preview is not None
    assert preview.plugin_name == "package"
    assert preview.version == "3.2.1"
    assert preview.author == "tester"


def test_preview_plugin_uses_factory_directory_as_plugin_root(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "nested.zip"
    create_zip(
        zip_path,
        {
            "outer/src/feature_factory.py": "",
            "outer/src/feature_const.py": "",
            "outer/src/plugin.json": json.dumps({"version": "1.0.0"}),
        },
    )

    preview = plugin_import_service.preview_plugin(zip_path)

    assert preview is not None
    assert preview.plugin_name == "src"
    assert preview.version == "1.0.0"


def test_preview_plugin_rejects_unrelated_factory_roots(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "multiple.zip"
    create_zip(
        zip_path,
        {
            "first/first_factory.py": "",
            "first/first_const.py": "",
            "second/second_factory.py": "",
            "second/second_const.py": "",
        },
    )

    assert plugin_import_service.preview_plugin(zip_path) is None


def test_preview_plugin_rejects_normalized_duplicate_path(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "duplicate.zip"
    create_zip(
        zip_path,
        {
            "package/package_factory.py": "",
            "package/package_const.py": 'PLUGIN_VERSION = "1.0.0"',
            "package/./package_const.py": 'PLUGIN_VERSION = "9.0.0"',
        },
    )

    assert plugin_import_service.preview_plugin(zip_path) is None


def test_preview_plugin_rejects_factory_without_same_directory_const(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "invalid.zip"
    create_zip(
        zip_path,
        {
            "package/features/feature_factory.py": "",
            "package/feature_const.py": "",
        },
    )

    assert plugin_import_service.preview_plugin(zip_path) is None


def test_preview_plugins_from_zip_returns_each_plugin_in_collection(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "bundle.zip"
    create_zip(
        zip_path,
        {
            "repository/first/first_factory.py": "",
            "repository/first/first_const.py": "",
            "repository/first/plugin.json": json.dumps(
                {"version": "1.0.0", "author": {"name": "first author"}}
            ),
            "repository/second/second_factory.py": "",
            "repository/second/second_const.py": "",
            "repository/second/plugin.json": json.dumps(
                {"version": "2.0.0", "author": {"name": "second author"}}
            ),
        },
    )

    previews = plugin_import_service.preview_plugins_from_zip(zip_path)

    assert [preview.plugin_name for preview in previews] == ["first", "second"]
    assert [preview.version for preview in previews] == ["1.0.0", "2.0.0"]
    assert [preview.author for preview in previews] == ["first author", "second author"]


def test_preview_plugin_ignores_const_plugin_fields(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "const_only.zip"
    create_zip(
        zip_path,
        {
            "package/package_factory.py": "",
            "package/package_const.py": (
                'PLUGIN_VERSION = "9.9.9"\n'
                'PLUGIN_AUTHOR = "from const"\n'
            ),
        },
    )

    preview = plugin_import_service.preview_plugin(zip_path)

    assert preview is not None
    assert preview.version is None
    assert preview.author is None


def test_preview_plugin_treats_invalid_manifest_as_missing(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "invalid_manifest.zip"
    create_zip(
        zip_path,
        {
            "package/package_factory.py": "",
            "package/package_const.py": "",
            "package/plugin.json": "{not json",
        },
    )

    preview = plugin_import_service.preview_plugin(zip_path)

    assert preview is not None
    assert preview.version is None
    assert preview.author is None


def test_preview_plugin_keeps_quotes_in_manifest_values(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "quotes.zip"
    create_zip(
        zip_path,
        {
            "package/package_factory.py": "",
            "package/package_const.py": "",
            "package/plugin.json": json.dumps(
                {"version": "1.0.0", "author": {"name": 'say "hi"'}}
            ),
        },
    )

    preview = plugin_import_service.preview_plugin(zip_path)

    assert preview is not None
    assert preview.author == 'say "hi"'


def test_preview_directory_reads_manifest(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "package"
    plugin_dir.mkdir()
    (plugin_dir / "package_factory.py").write_text("", encoding="utf-8")
    (plugin_dir / "package_const.py").write_text(
        'PLUGIN_VERSION = "9.9.9"\n', encoding="utf-8"
    )
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"version": "1.2.3", "author": {"name": "dir author"}}),
        encoding="utf-8",
    )

    preview = plugin_import_service.preview_directory(plugin_dir)

    assert preview is not None
    assert preview.version == "1.2.3"
    assert preview.author == "dir author"

    previews = plugin_import_service.preview_plugins_from_directory(plugin_dir)

    assert [item.version for item in previews] == ["1.2.3"]
