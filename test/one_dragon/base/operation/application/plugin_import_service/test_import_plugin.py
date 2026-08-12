from collections.abc import Callable
from pathlib import Path

import pytest

import one_dragon.base.operation.application.plugin_import_service as plugin_import_service_module
from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)


def test_import_wrapped_plugin_uses_primary_factory_directory(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "wrapped.zip"
    create_zip(
        zip_path,
        {
            "./": "",
            "repository-main/README.md": "不属于插件",
            "repository-main/registry.json": "不属于插件",
            "repository-main/my_plugin/my_plugin_factory.py": "",
            "repository-main/my_plugin/my_plugin_const.py": 'PLUGIN_VERSION = "2.0.0"',
            "repository-main/my_plugin/operations/task.py": "",
            "repository-main/my_plugin/extra/extra_factory.py": "",
            "__MACOSX/._my_plugin": "",
            ".DS_Store": "",
        },
    )

    result = plugin_import_service.import_plugin(zip_path)

    plugin_dir = plugin_import_service.plugins_dir / "my_plugin"
    assert result.success
    assert result.plugin_name == "my_plugin"
    assert (plugin_dir / "my_plugin_factory.py").exists()
    assert (plugin_dir / "operations" / "task.py").exists()
    assert (plugin_dir / "extra" / "extra_factory.py").exists()
    assert not (plugin_dir / "repository-main").exists()
    assert not (plugin_dir / "README.md").exists()
    assert not (plugin_dir / "registry.json").exists()


def test_import_plugin_uses_root_factory_name_when_factory_is_at_zip_root(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "root.zip"
    create_zip(
        zip_path,
        {
            "root_app_factory.py": "",
            "root_app_const.py": "",
            "operations/task.py": "",
        },
    )

    result = plugin_import_service.import_plugin(zip_path)

    assert result.success
    assert result.plugin_name == "root_app"
    assert (plugin_import_service.plugins_dir / "root_app" / "root_app_factory.py").exists()
    assert (plugin_import_service.plugins_dir / "root_app" / "operations" / "task.py").exists()


def test_import_plugin_rejects_unrelated_factory_roots(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "multiple.zip"
    create_zip(
        zip_path,
        {
            "bundle/first/first_factory.py": "",
            "bundle/first/first_const.py": "",
            "bundle/second/second_factory.py": "",
            "bundle/second/second_const.py": "",
        },
    )

    result = plugin_import_service.import_plugin(zip_path)

    assert not result.success
    assert "多个互不隶属的插件" in result.message


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../../escaped.txt",
        "/escaped.txt",
        "C:/escaped.txt",
        "..\\..\\escaped.txt",
    ],
)
def test_import_plugin_rejects_unsafe_member_path(
    unsafe_path: str,
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "unsafe.zip"
    create_zip(
        zip_path,
        {
            "unsafe/unsafe_factory.py": "",
            "unsafe/unsafe_const.py": "",
            unsafe_path: "bad",
        },
    )

    result = plugin_import_service.import_plugin(zip_path)

    assert not result.success
    assert "不安全" in result.message
    assert not (tmp_path / "escaped.txt").exists()


def test_import_plugin_rejects_normalized_duplicate_path(
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

    result = plugin_import_service.import_plugin(zip_path)

    assert not result.success
    assert "重复路径" in result.message


@pytest.mark.parametrize(
    "extra_file",
    [
        "package/second_factory.py",
        "package/second_const.py",
    ],
)
def test_import_plugin_rejects_same_directory_factory_or_const_conflict(
    extra_file: str,
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "conflict.zip"
    create_zip(
        zip_path,
        {
            "package/package_factory.py": "",
            "package/package_const.py": "",
            extra_file: "",
        },
    )

    result = plugin_import_service.import_plugin(zip_path)

    assert not result.success
    assert "插件根目录不能包含多个" in result.message


def test_import_plugin_rejects_missing_const(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "missing_const.zip"
    create_zip(zip_path, {"missing/missing_factory.py": ""})

    result = plugin_import_service.import_plugin(zip_path)

    assert not result.success
    assert "缺少 *_const.py" in result.message


def test_import_plugin_rejects_oversized_extracted_content(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "large.zip"
    create_zip(
        zip_path,
        {
            "large/large_factory.py": "",
            "large/large_const.py": "",
            "large/data.bin": "12",
        },
    )
    monkeypatch.setattr(plugin_import_service_module, "_MAX_EXTRACT_SIZE", 1)

    result = plugin_import_service.import_plugin(zip_path)

    assert not result.success
    assert "解压后体积过大" in result.message
    assert not (plugin_import_service.plugins_dir / "large").exists()


def test_import_plugin_rejects_existing_target_file(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    target_file = plugin_import_service.plugins_dir / "keep"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("keep", encoding="utf-8")

    zip_path = tmp_path / "keep.zip"
    create_zip(
        zip_path,
        {
            "keep/keep_factory.py": "",
            "keep/keep_const.py": "",
        },
    )

    result = plugin_import_service.import_plugin(zip_path, overwrite=True)

    assert not result.success
    assert target_file.read_text(encoding="utf-8") == "keep"


def test_import_plugin_keeps_old_version_when_extraction_fails(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_dir = plugin_import_service.plugins_dir / "keep"
    target_dir.mkdir(parents=True)
    old_file = target_dir / "old.txt"
    old_file.write_text("old", encoding="utf-8")

    zip_path = tmp_path / "keep.zip"
    create_zip(
        zip_path,
        {
            "keep/keep_factory.py": "",
            "keep/keep_const.py": "",
        },
    )

    def fail_extract(*args: object, **kwargs: object) -> None:
        raise OSError("模拟解压失败")

    monkeypatch.setattr(plugin_import_service, "_extract_plugin", fail_extract)

    result = plugin_import_service.import_plugin(zip_path, overwrite=True)

    assert not result.success
    assert old_file.read_text(encoding="utf-8") == "old"


def test_import_plugin_restores_old_version_when_swap_fails(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_dir = plugin_import_service.plugins_dir / "keep"
    target_dir.mkdir(parents=True)
    old_file = target_dir / "old.txt"
    old_file.write_text("old", encoding="utf-8")

    zip_path = tmp_path / "keep.zip"
    create_zip(
        zip_path,
        {
            "keep/keep_factory.py": "",
            "keep/keep_const.py": "",
        },
    )

    original_replace = Path.replace

    def fail_staging_replace(path: Path, target: Path) -> Path:
        if path.name.startswith(".keep.tmp-"):
            raise OSError("模拟替换失败")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_staging_replace)

    result = plugin_import_service.import_plugin(zip_path, overwrite=True)

    assert not result.success
    assert old_file.read_text(encoding="utf-8") == "old"


def test_import_plugins_from_zip_installs_each_outermost_plugin_root(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "bundle.zip"
    create_zip(
        zip_path,
        {
            "repository/README.md": "不安装",
            "repository/first/first_factory.py": "",
            "repository/first/first_const.py": 'PLUGIN_VERSION = "1.0.0"',
            "repository/first/assets/first.txt": "first",
            "repository/second/second_factory.py": "",
            "repository/second/second_const.py": 'PLUGIN_VERSION = "2.0.0"',
            "repository/second/assets/second.txt": "second",
        },
    )

    results = plugin_import_service.import_plugins_from_zip(zip_path)

    assert [result.plugin_name for result in results] == ["first", "second"]
    assert all(result.success for result in results)
    assert (plugin_import_service.plugins_dir / "first" / "assets" / "first.txt").exists()
    assert (plugin_import_service.plugins_dir / "second" / "assets" / "second.txt").exists()
    assert not (plugin_import_service.plugins_dir / "repository").exists()


def test_import_plugins_from_zip_does_not_split_nested_plugin_root(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "root.zip"
    create_zip(
        zip_path,
        {
            "root_factory.py": "",
            "root_const.py": "",
            "nested/nested_factory.py": "",
            "nested/nested_const.py": "",
        },
    )

    results = plugin_import_service.import_plugins_from_zip(zip_path)

    assert len(results) == 1
    assert results[0].success
    assert results[0].plugin_name == "root"
    assert (plugin_import_service.plugins_dir / "root" / "nested" / "nested_factory.py").exists()
    assert not (plugin_import_service.plugins_dir / "nested").exists()


def test_import_plugins_from_zip_rejects_case_insensitive_duplicate_names_before_writing(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "duplicate_names.zip"
    create_zip(
        zip_path,
        {
            "one/Same/Same_factory.py": "",
            "one/Same/Same_const.py": "",
            "two/same/same_factory.py": "",
            "two/same/same_const.py": "",
        },
    )

    results = plugin_import_service.import_plugins_from_zip(zip_path)

    assert len(results) == 1
    assert not results[0].success
    assert "重复插件目录名" in results[0].message
    assert not plugin_import_service.plugins_dir.exists()


def test_import_plugins_from_zip_applies_total_size_limit(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "large_bundle.zip"
    create_zip(
        zip_path,
        {
            "first/first_factory.py": "",
            "first/first_const.py": "",
            "first/data.bin": "12",
            "second/second_factory.py": "",
            "second/second_const.py": "",
            "second/data.bin": "34",
        },
    )
    monkeypatch.setattr(plugin_import_service_module, "_MAX_EXTRACT_SIZE", 3)

    results = plugin_import_service.import_plugins_from_zip(zip_path)

    assert len(results) == 1
    assert not results[0].success
    assert "解压后体积过大" in results[0].message
    assert not plugin_import_service.plugins_dir.exists()


def test_import_plugins_from_zip_only_overwrites_selected_existing_plugin(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    first_target = plugin_import_service.plugins_dir / "first"
    first_target.mkdir(parents=True)
    (first_target / "old.txt").write_text("old", encoding="utf-8")

    zip_path = tmp_path / "bundle.zip"
    create_zip(
        zip_path,
        {
            "first/first_factory.py": "",
            "first/first_const.py": "",
            "first/new.txt": "new",
            "second/second_factory.py": "",
            "second/second_const.py": "",
            "second/data.txt": "original",
        },
    )

    first_results = plugin_import_service.import_plugins_from_zip(zip_path)
    assert [result.success for result in first_results] == [False, True]
    second_marker = plugin_import_service.plugins_dir / "second" / "data.txt"
    second_marker.write_text("keep", encoding="utf-8")

    overwrite_results = plugin_import_service.import_plugins_from_zip(
        zip_path,
        overwrite=True,
        selected_plugin_names={"first"},
    )

    assert len(overwrite_results) == 1
    assert overwrite_results[0].success
    assert overwrite_results[0].plugin_name == "first"
    assert not (first_target / "old.txt").exists()
    assert (first_target / "new.txt").read_text(encoding="utf-8") == "new"
    assert second_marker.read_text(encoding="utf-8") == "keep"


def test_import_plugins_from_zip_keeps_results_independent_when_one_extract_fails(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    broken_target = plugin_import_service.plugins_dir / "broken"
    broken_target.mkdir(parents=True)
    old_file = broken_target / "old.txt"
    old_file.write_text("old", encoding="utf-8")

    zip_path = tmp_path / "bundle.zip"
    create_zip(
        zip_path,
        {
            "broken/broken_factory.py": "",
            "broken/broken_const.py": "",
            "good/good_factory.py": "",
            "good/good_const.py": "",
        },
    )
    original_extract = plugin_import_service._extract_plugin
    original_remove = plugin_import_service._remove_path

    def fail_broken(*args: object, **kwargs: object) -> None:
        target_dir = args[1]
        assert isinstance(target_dir, Path)
        if target_dir.name.startswith(".broken.tmp-"):
            raise OSError("模拟单个插件解压失败")
        original_extract(*args, **kwargs)

    def fail_broken_cleanup(path: Path) -> None:
        if path.name.startswith(".broken.tmp-"):
            raise OSError("模拟单个插件临时目录清理失败")
        original_remove(path)

    monkeypatch.setattr(plugin_import_service, "_extract_plugin", fail_broken)
    monkeypatch.setattr(plugin_import_service, "_remove_path", fail_broken_cleanup)

    results = plugin_import_service.import_plugins_from_zip(zip_path, overwrite=True)

    assert [result.success for result in results] == [False, True]
    assert old_file.read_text(encoding="utf-8") == "old"
    assert (plugin_import_service.plugins_dir / "good" / "good_factory.py").exists()
