import sys
import types
from pathlib import Path

import pytest

from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)


def _build_context_stub(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    module_file: Path,
) -> object:
    """构造一个定义在指定文件路径上的上下文类实例。"""
    module = types.ModuleType(module_name)
    module.__file__ = str(module_file)
    monkeypatch.setitem(sys.modules, module_name, module)
    stub_context_class = type("StubContext", (), {"__module__": module_name})
    return stub_context_class()


def test_plugins_dir_uses_last_src_segment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """路径中出现多个 src 段时，插件目录应与 find_src_dir 的结果保持一致。"""
    module_file = tmp_path / "src" / "project" / "src" / "pkg" / "impl.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("", encoding="utf-8")
    service = PluginImportService(
        _build_context_stub(monkeypatch, "stub_plugin_ctx_last_src", module_file)
    )

    assert service.plugins_dir == tmp_path / "src" / "project" / "plugins"


def test_plugins_dir_raises_when_src_directory_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """路径中没有 src 段时，插件目录无法确定，应明确报错。"""
    module_file = tmp_path / "pkg" / "impl.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("", encoding="utf-8")
    service = PluginImportService(
        _build_context_stub(monkeypatch, "stub_plugin_ctx_no_src", module_file)
    )

    with pytest.raises(ValueError, match="插件导入不可用"):
        _ = service.plugins_dir
