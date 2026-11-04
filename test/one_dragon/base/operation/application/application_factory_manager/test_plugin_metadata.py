import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginInfo, PluginSource

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext

_FACTORY_SOURCE = """
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from . import const


class PluginFactory(ApplicationFactory):
    def __init__(self, ctx):
        ApplicationFactory.__init__(self, const)

    def create_application(self, instance_idx, group_id):
        return None

    def create_config(self, instance_idx, group_id):
        return None
"""


def _write_plugin(
    plugins_dir: Path,
    app_id: str,
    manifest: Any = None,
    extra_const: str = "",
) -> Path:
    plugin_dir = plugins_dir / app_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text("", encoding="utf-8")
    (plugin_dir / "const.py").write_text(
        f'APP_ID = "{app_id}"\nAPP_NAME = "{app_id}"\n'
        f"DEFAULT_GROUP = False\nNEED_NOTIFY = False\n{extra_const}",
        encoding="utf-8",
    )
    (plugin_dir / "factory.py").write_text(
        _FACTORY_SOURCE, encoding="utf-8"
    )
    if manifest is not None:
        text = manifest if isinstance(manifest, str) else json.dumps(manifest)
        (plugin_dir / "plugin.json").write_text(text, encoding="utf-8")
    return plugin_dir


def _discover(plugins_dir: Path) -> ApplicationFactoryManager:
    manager = ApplicationFactoryManager(
        cast("OneDragonContext", object()),
        [(plugins_dir, PluginSource.THIRD_PARTY)],
    )
    manager.discover_factories()
    return manager


def _info(manager: ApplicationFactoryManager, app_id: str) -> PluginInfo:
    info = manager.get_plugin_info(app_id)
    assert info is not None
    return info


def test_metadata_comes_from_manifest_not_const(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugin_dir = _write_plugin(
        plugins_dir,
        "meta_from_json",
        {
            "version": "1.0.0",
            "author": {"name": "json author"},
            "homepage": "https://github.com/a/b",
            "summary": "json summary",
            "cover": "cover.png",
        },
        extra_const='PLUGIN_VERSION = "0.0.1"\nPLUGIN_AUTHOR = "const author"\n',
    )
    (plugin_dir / "cover.png").write_bytes(b"png")

    info = _info(_discover(plugins_dir), "meta_from_json")

    assert info.version == "1.0.0"
    assert info.author == "json author"
    assert info.homepage == "https://github.com/a/b"
    assert info.description == "json summary"
    assert info.cover_path == (plugin_dir / "cover.png").resolve()


def test_missing_manifest_leaves_metadata_empty(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    _write_plugin(plugins_dir, "meta_no_json", extra_const='PLUGIN_VERSION = "7.7.7"\n')

    manager = _discover(plugins_dir)
    info = _info(manager, "meta_no_json")

    assert (info.version, info.author, info.homepage, info.description) == ("", "", "", "")
    assert info.cover_path is None
    assert manager.scan_failures == []


def test_invalid_manifest_does_not_break_loading(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    _write_plugin(plugins_dir, "meta_bad_json", "{not json")

    manager = _discover(plugins_dir)
    info = _info(manager, "meta_bad_json")

    assert info.version == ""
    assert info.cover_path is None
    assert manager.scan_failures == []


def test_cover_path_outside_plugin_dir_is_ignored(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    _write_plugin(plugins_dir, "meta_bad_cover", {"version": "1.0.0", "cover": "../outside.png"})
    (plugins_dir / "outside.png").write_bytes(b"png")

    info = _info(_discover(plugins_dir), "meta_bad_cover")

    assert info.version == "1.0.0"
    assert info.cover_path is None
