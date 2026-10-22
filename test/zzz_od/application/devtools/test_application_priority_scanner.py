from pathlib import Path

import pytest

from zzz_od.application.devtools.application_priority_scanner import _scan_directory


def test_third_party_scan_only_reads_plugin_root_factory(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "root_plugin"
    nested_dir = plugin_dir / "nested"
    nested_dir.mkdir(parents=True)
    (plugin_dir / "root_factory.py").write_text("", encoding="utf-8")
    (plugin_dir / "root_const.py").write_text(
        'APP_ID = "root"\nAPP_NAME = "根插件"\nDEFAULT_GROUP = False\n',
        encoding="utf-8",
    )
    (nested_dir / "nested_factory.py").write_text("", encoding="utf-8")
    (nested_dir / "nested_const.py").write_text(
        'APP_ID = "nested"\nAPP_NAME = "嵌套插件"\nDEFAULT_GROUP = False\n',
        encoding="utf-8",
    )

    items, errors = _scan_directory(plugins_dir, "third_party", tmp_path)

    assert [item.app_id for item in items] == ["root"]
    assert errors == []


def test_third_party_scan_returns_error_when_root_resolve_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    original_resolve = Path.resolve

    def fail_plugins_resolve(path: Path, strict: bool = False) -> Path:
        if path == plugins_dir:
            raise OSError("模拟插件根解析失败")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", fail_plugins_resolve)

    items, errors = _scan_directory(plugins_dir, "third_party", tmp_path)

    assert items == []
    assert errors == ["plugins: OSError: 模拟插件根解析失败"]


def test_third_party_scan_skips_plugin_directory_resolved_outside_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "linked_plugin"
    outside_dir = tmp_path / "outside"
    plugin_dir.mkdir(parents=True)
    outside_dir.mkdir()
    (plugin_dir / "linked_factory.py").write_text("", encoding="utf-8")
    (plugin_dir / "linked_const.py").write_text(
        'APP_ID = "linked"\nAPP_NAME = "外部插件"\nDEFAULT_GROUP = False\n',
        encoding="utf-8",
    )
    original_resolve = Path.resolve

    def redirect_plugin_dir(path: Path, strict: bool = False) -> Path:
        if path == plugin_dir:
            return outside_dir
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", redirect_plugin_dir)

    items, errors = _scan_directory(plugins_dir, "third_party", tmp_path)

    assert items == []
    assert errors == []


def test_third_party_scan_records_plugin_filesystem_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugins_dir = tmp_path / "plugins"
    bad_dir = plugins_dir / "bad_plugin"
    good_dir = plugins_dir / "good_plugin"
    bad_dir.mkdir(parents=True)
    good_dir.mkdir()
    (good_dir / "good_factory.py").write_text("", encoding="utf-8")
    (good_dir / "good_const.py").write_text(
        'APP_ID = "good"\nAPP_NAME = "正常插件"\nDEFAULT_GROUP = False\n',
        encoding="utf-8",
    )
    original_resolve = Path.resolve
    original_glob = Path.glob

    def fail_bad_resolve(path: Path, strict: bool = False) -> Path:
        if path == bad_dir:
            raise OSError("模拟插件目录解析失败")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", fail_bad_resolve)
    items, errors = _scan_directory(plugins_dir, "third_party", tmp_path)
    assert [item.app_id for item in items] == ["good"]
    assert errors == [
        f"{bad_dir.relative_to(tmp_path)}: OSError: 模拟插件目录解析失败"
    ]

    monkeypatch.setattr(Path, "resolve", original_resolve)

    def fail_bad_glob(path: Path, pattern: str):
        if path == bad_dir:
            raise OSError("模拟插件文件枚举失败")
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", fail_bad_glob)
    items, errors = _scan_directory(plugins_dir, "third_party", tmp_path)

    assert [item.app_id for item in items] == ["good"]
    assert errors == [
        f"{bad_dir.relative_to(tmp_path)}: OSError: 模拟插件文件枚举失败"
    ]


def test_builtin_scan_keeps_recursive_factory_discovery(tmp_path: Path) -> None:
    application_dir = tmp_path / "src" / "zzz_od" / "application"
    nested_dir = application_dir / "group" / "nested_app"
    nested_dir.mkdir(parents=True)
    (nested_dir / "nested_factory.py").write_text("", encoding="utf-8")
    (nested_dir / "nested_const.py").write_text(
        'APP_ID = "nested"\nAPP_NAME = "内置应用"\nDEFAULT_GROUP = False\n',
        encoding="utf-8",
    )

    items, errors = _scan_directory(application_dir, "builtin", tmp_path)

    assert [item.app_id for item in items] == ["nested"]
    assert errors == []
