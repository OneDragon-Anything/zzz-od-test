from pathlib import Path

import pytest

import one_dragon.base.operation.application.plugin_import_service as plugin_import_service_module
from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)


def test_import_directory_ignores_nested_factory_validation(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "directory_plugin"
    source_dir.mkdir()
    (source_dir / "plugin_factory.py").write_text("", encoding="utf-8")
    (source_dir / "plugin_const.py").write_text(
        'PLUGIN_VERSION = "1.0.0"',
        encoding="utf-8",
    )
    feature_dir = source_dir / "features" / "one"
    feature_dir.mkdir(parents=True)
    (feature_dir / "one_factory.py").write_text("", encoding="utf-8")

    result = plugin_import_service.import_directory(source_dir)

    plugin_dir = plugin_import_service.plugins_dir / "directory_plugin"
    assert result.success
    assert (plugin_dir / "plugin_factory.py").exists()
    assert (plugin_dir / "features" / "one" / "one_factory.py").exists()


def test_import_directory_rejects_factory_only_in_nested_directory(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "nested_only"
    feature_dir = source_dir / "features" / "one"
    feature_dir.mkdir(parents=True)
    (feature_dir / "one_factory.py").write_text("", encoding="utf-8")
    (feature_dir / "one_const.py").write_text("", encoding="utf-8")

    result = plugin_import_service.import_directory(source_dir)

    assert not result.success
    assert "插件根目录缺少 *_factory.py" in result.message


@pytest.mark.parametrize(
    "extra_file_name",
    [
        "second_factory.py",
        "second_const.py",
    ],
)
def test_import_directory_rejects_same_directory_factory_or_const_conflict(
    extra_file_name: str,
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "conflict"
    source_dir.mkdir()
    (source_dir / "plugin_factory.py").write_text("", encoding="utf-8")
    (source_dir / "plugin_const.py").write_text("", encoding="utf-8")
    (source_dir / extra_file_name).write_text("", encoding="utf-8")

    result = plugin_import_service.import_directory(source_dir)

    assert not result.success
    assert "插件根目录不能包含多个" in result.message


def test_import_directory_rejects_missing_const(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "missing_const"
    source_dir.mkdir()
    (source_dir / "missing_factory.py").write_text("", encoding="utf-8")

    result = plugin_import_service.import_directory(source_dir)

    assert not result.success
    assert "缺少 *_const.py" in result.message


def test_import_directory_keeps_old_version_when_copy_fails(
    plugin_import_service: PluginImportService,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_dir = plugin_import_service.plugins_dir / "keep"
    target_dir.mkdir(parents=True)
    old_file = target_dir / "old.txt"
    old_file.write_text("old", encoding="utf-8")

    source_dir = tmp_path / "keep"
    source_dir.mkdir()
    (source_dir / "keep_factory.py").write_text("", encoding="utf-8")
    (source_dir / "keep_const.py").write_text("", encoding="utf-8")

    def fail_copy(*args: object, **kwargs: object) -> None:
        raise OSError("模拟复制失败")

    monkeypatch.setattr(plugin_import_service_module.shutil, "copytree", fail_copy)

    result = plugin_import_service.import_directory(source_dir, overwrite=True)

    assert not result.success
    assert old_file.read_text(encoding="utf-8") == "old"


def test_import_plugins_from_directory_installs_each_outermost_plugin_root(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "collection"
    first_dir = source_dir / "repository" / "first"
    second_dir = source_dir / "repository" / "second"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    (source_dir / "repository" / "README.md").write_text("不安装", encoding="utf-8")
    (first_dir / "first_factory.py").write_text("", encoding="utf-8")
    (first_dir / "first_const.py").write_text('PLUGIN_VERSION = "1.0.0"', encoding="utf-8")
    (first_dir / "first.txt").write_text("first", encoding="utf-8")
    (second_dir / "second_factory.py").write_text("", encoding="utf-8")
    (second_dir / "second_const.py").write_text('PLUGIN_VERSION = "2.0.0"', encoding="utf-8")
    (second_dir / "second.txt").write_text("second", encoding="utf-8")

    previews = plugin_import_service.preview_plugins_from_directory(source_dir)
    results = plugin_import_service.import_plugins_from_directory(source_dir)

    assert [preview.plugin_name for preview in previews] == ["first", "second"]
    assert [preview.version for preview in previews] == ["1.0.0", "2.0.0"]
    assert [result.plugin_name for result in results] == ["first", "second"]
    assert all(result.success for result in results)
    assert (plugin_import_service.plugins_dir / "first" / "first.txt").exists()
    assert (plugin_import_service.plugins_dir / "second" / "second.txt").exists()
    assert not (plugin_import_service.plugins_dir / "repository").exists()


def test_import_plugins_from_directory_does_not_split_nested_plugin_root(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "root_plugin"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True)
    (source_dir / "root_factory.py").write_text("", encoding="utf-8")
    (source_dir / "root_const.py").write_text("", encoding="utf-8")
    (nested_dir / "nested_factory.py").write_text("", encoding="utf-8")
    (nested_dir / "nested_const.py").write_text("", encoding="utf-8")

    results = plugin_import_service.import_plugins_from_directory(source_dir)

    assert len(results) == 1
    assert results[0].success
    assert results[0].plugin_name == "root_plugin"
    assert (plugin_import_service.plugins_dir / "root_plugin" / "nested" / "nested_factory.py").exists()
    assert not (plugin_import_service.plugins_dir / "nested").exists()


def test_import_plugins_from_directory_rejects_duplicate_names_before_writing(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "duplicate_names"
    first_dir = source_dir / "one" / "Same"
    second_dir = source_dir / "two" / "same"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    (first_dir / "Same_factory.py").write_text("", encoding="utf-8")
    (first_dir / "Same_const.py").write_text("", encoding="utf-8")
    (second_dir / "same_factory.py").write_text("", encoding="utf-8")
    (second_dir / "same_const.py").write_text("", encoding="utf-8")

    results = plugin_import_service.import_plugins_from_directory(source_dir)

    assert len(results) == 1
    assert not results[0].success
    assert "重复插件目录名" in results[0].message
    assert not plugin_import_service.plugins_dir.exists()


def test_import_plugins_from_directory_only_overwrites_selected_plugin(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    first_target = plugin_import_service.plugins_dir / "first"
    first_target.mkdir(parents=True)
    (first_target / "old.txt").write_text("old", encoding="utf-8")

    source_dir = tmp_path / "collection"
    first_dir = source_dir / "first"
    second_dir = source_dir / "second"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    (first_dir / "first_factory.py").write_text("", encoding="utf-8")
    (first_dir / "first_const.py").write_text("", encoding="utf-8")
    (first_dir / "new.txt").write_text("new", encoding="utf-8")
    (second_dir / "second_factory.py").write_text("", encoding="utf-8")
    (second_dir / "second_const.py").write_text("", encoding="utf-8")
    (second_dir / "data.txt").write_text("original", encoding="utf-8")

    first_results = plugin_import_service.import_plugins_from_directory(source_dir)
    assert [result.success for result in first_results] == [False, True]
    second_marker = plugin_import_service.plugins_dir / "second" / "data.txt"
    second_marker.write_text("keep", encoding="utf-8")

    overwrite_results = plugin_import_service.import_plugins_from_directory(
        source_dir,
        overwrite=True,
        selected_plugin_names={"first"},
    )

    assert len(overwrite_results) == 1
    assert overwrite_results[0].success
    assert overwrite_results[0].plugin_name == "first"
    assert not (first_target / "old.txt").exists()
    assert (first_target / "new.txt").read_text(encoding="utf-8") == "new"
    assert second_marker.read_text(encoding="utf-8") == "keep"


def test_import_plugins_from_directory_rejects_symlink_outside_plugin_root(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "collection"
    plugin_dir = source_dir / "linked"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "linked_factory.py").write_text("", encoding="utf-8")
    (plugin_dir / "linked_const.py").write_text("", encoding="utf-8")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")
    try:
        (plugin_dir / "outside.txt").symlink_to(outside_file)
    except OSError:
        pytest.skip("当前环境不允许创建符号链接")

    results = plugin_import_service.import_plugins_from_directory(source_dir)

    assert len(results) == 1
    assert not results[0].success
    assert "越界符号链接" in results[0].message
    assert not plugin_import_service.plugins_dir.exists()


def test_import_plugins_from_directory_rejects_symlink_factory_inside_plugin_root(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "collection"
    plugin_dir = source_dir / "linked"
    nested_dir = plugin_dir / "nested"
    nested_dir.mkdir(parents=True)
    real_factory = nested_dir / "real_factory.py"
    real_factory.write_text("", encoding="utf-8")
    (plugin_dir / "linked_const.py").write_text("", encoding="utf-8")
    try:
        (plugin_dir / "linked_factory.py").symlink_to(real_factory)
    except OSError:
        pytest.skip("当前环境不允许创建文件符号链接")

    results = plugin_import_service.import_plugins_from_directory(source_dir)

    assert len(results) == 1
    assert not results[0].success
    assert "插件根第一层 Python 文件不能是符号链接" in results[0].message
    assert not plugin_import_service.plugins_dir.exists()


def test_import_plugins_from_directory_rejects_multi_node_symlink_loop(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "collection"
    plugin_dir = source_dir / "linked"
    first_dir = plugin_dir / "first"
    second_dir = plugin_dir / "second"
    first_dir.mkdir(parents=True)
    second_dir.mkdir()
    (plugin_dir / "linked_factory.py").write_text("", encoding="utf-8")
    (plugin_dir / "linked_const.py").write_text("", encoding="utf-8")
    try:
        (first_dir / "to_second").symlink_to(second_dir, target_is_directory=True)
        (second_dir / "to_first").symlink_to(first_dir, target_is_directory=True)
    except OSError:
        pytest.skip("当前环境不允许创建目录符号链接")

    results = plugin_import_service.import_plugins_from_directory(source_dir)

    assert len(results) == 1
    assert not results[0].success
    assert "循环符号链接" in results[0].message
    assert not plugin_import_service.plugins_dir.exists()


def test_import_plugins_from_directory_allows_internal_directory_symlink(
    plugin_import_service: PluginImportService,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "collection"
    plugin_dir = source_dir / "linked"
    assets_dir = plugin_dir / "assets"
    assets_dir.mkdir(parents=True)
    (plugin_dir / "linked_factory.py").write_text("", encoding="utf-8")
    (plugin_dir / "linked_const.py").write_text("", encoding="utf-8")
    (assets_dir / "data.txt").write_text("data", encoding="utf-8")
    try:
        (plugin_dir / "linked_assets").symlink_to(
            assets_dir,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("当前环境不允许创建目录符号链接")

    results = plugin_import_service.import_plugins_from_directory(source_dir)

    assert len(results) == 1
    assert results[0].success
    imported_file = (
        plugin_import_service.plugins_dir / "linked" / "linked_assets" / "data.txt"
    )
    assert imported_file.read_text(encoding="utf-8") == "data"
    assert not imported_file.is_symlink()


def test_import_plugins_from_directory_keeps_results_independent_when_one_copy_fails(
    plugin_import_service: PluginImportService,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    broken_target = plugin_import_service.plugins_dir / "broken"
    broken_target.mkdir(parents=True)
    old_file = broken_target / "old.txt"
    old_file.write_text("old", encoding="utf-8")

    source_dir = tmp_path / "collection"
    broken_dir = source_dir / "broken"
    good_dir = source_dir / "good"
    broken_dir.mkdir(parents=True)
    good_dir.mkdir(parents=True)
    (broken_dir / "broken_factory.py").write_text("", encoding="utf-8")
    (broken_dir / "broken_const.py").write_text("", encoding="utf-8")
    (good_dir / "good_factory.py").write_text("", encoding="utf-8")
    (good_dir / "good_const.py").write_text("", encoding="utf-8")
    original_copytree = plugin_import_service_module.shutil.copytree

    def fail_broken(source: Path, target: Path) -> Path:
        if source.name == "broken":
            raise OSError("模拟单个插件复制失败")
        return original_copytree(source, target)

    monkeypatch.setattr(plugin_import_service_module.shutil, "copytree", fail_broken)

    results = plugin_import_service.import_plugins_from_directory(source_dir, overwrite=True)

    assert [result.success for result in results] == [False, True]
    assert old_file.read_text(encoding="utf-8") == "old"
    assert (plugin_import_service.plugins_dir / "good" / "good_factory.py").exists()
