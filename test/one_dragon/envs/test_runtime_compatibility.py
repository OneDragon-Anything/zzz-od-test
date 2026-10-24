"""验证运行时兼容性检查，不依赖 Git 仓库或目标提交。"""

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.envs.runtime_compatibility import (
    check_manifest_compatible,
    load_runtime_manifest,
)


@pytest.mark.parametrize('manifest', [b'import sys\n', b''])
def test_load_runtime_manifest_reads_bundled_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest: bytes,
) -> None:
    """从冻结运行时目录读取原始清单，空文件也作为有效基准返回。"""
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    (tmp_path / 'module_manifest.py').write_bytes(manifest)

    assert load_runtime_manifest() == manifest


def test_non_frozen_environment_does_not_read_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """源码模式不访问打包清单路径。"""
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    path = Mock(side_effect=AssertionError('源码模式不应读取打包清单'))
    monkeypatch.setattr('one_dragon.envs.runtime_compatibility.Path', path)

    assert load_runtime_manifest() is None
    path.assert_not_called()


def test_missing_bundled_manifest_skips_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧打包产物缺少清单时继续跳过检查。"""
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)

    assert load_runtime_manifest() is None


def test_unreadable_bundled_manifest_skips_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """清单读取失败时维持原有跳过行为。"""
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    (tmp_path / 'module_manifest.py').write_bytes(b'import sys\n')
    monkeypatch.setattr(Path, 'read_bytes', Mock(side_effect=PermissionError('无法读取')))

    assert load_runtime_manifest() is None


@pytest.mark.parametrize(
    ('local', 'remote'),
    [
        (b'import sys\n', b'import sys\n'),
        (b'import sys\r\n', b'import sys\n'),
        (b'import sys\r', b'import sys\n'),
        (b'import sys\n', b'# comment\nimport sys\n'),
        (b'import sys\nimport os\n', b'import os\nimport sys\n'),
        (b'import sys\nimport os\n', b'import sys, os\n'),
        (b'import sys\n', b'import sys as runtime\n'),
        (b'import sys\nimport optional_dependency\n', b'import sys\n'),
        (b'from math import pi, tau\n', b'from math import pi\n'),
        (b'from math import pi, tau\n', b'from math import tau as value\nfrom math import pi\n'),
        (b'from math import pi\n', b'import math\n'),
        (b'import sys\n', b"import sys\nif not getattr(sys, 'frozen', False):\n    import sys\n"),
    ],
)
def test_equivalent_or_reduced_imports_do_not_probe(
    monkeypatch: pytest.MonkeyPatch,
    local: bytes,
    remote: bytes,
) -> None:
    """格式变化、别名和删除依赖不触发导入或阻止更新。"""
    importer = Mock(side_effect=AssertionError('不应导入已有依赖'))
    monkeypatch.setattr(
        'one_dragon.envs.runtime_compatibility.importlib',
        SimpleNamespace(import_module=importer),
    )

    assert check_manifest_compatible(local, remote) is True
    importer.assert_not_called()


@pytest.mark.parametrize(
    ('local', 'remote'),
    [
        (b'import sys\n', b'import sys\nimport json\n'),
        (b'import math\n', b'from math import pi, tau\n'),
        (b'from math import pi\n', b'from math import pi, isfinite\n'),
        (b'import PySide6.QtCore\n', b'from PySide6.QtCore import QTimer\n'),
    ],
)
def test_existing_runtime_modules_and_symbols_are_accepted(
    local: bytes,
    remote: bytes,
) -> None:
    """新增导入可由现有标准库或二进制扩展满足时允许更新。"""
    assert check_manifest_compatible(local, remote) is True


def test_only_added_names_are_probed(monkeypatch: pytest.MonkeyPatch) -> None:
    """不重新加载本地清单中的可选依赖及已有导入名称。"""
    dependency = SimpleNamespace(added=object())
    importer = Mock(return_value=dependency)
    monkeypatch.setattr(
        'one_dragon.envs.runtime_compatibility.importlib',
        SimpleNamespace(import_module=importer),
    )

    assert check_manifest_compatible(
        b'import unavailable_optional\nfrom dependency import existing\n',
        b'import unavailable_optional\nfrom dependency import existing, added\n',
    ) is True
    importer.assert_called_once_with('dependency')


def test_from_import_can_load_an_unloaded_submodule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """包上还没有同名属性时继续尝试加载其子模块。"""
    package = ModuleType('runtime_dependency')
    child = ModuleType('runtime_dependency.child')

    def import_module(name: str) -> ModuleType:
        """模拟正常导入给父包补上子模块属性。"""
        if name == 'runtime_dependency':
            return package
        assert name == 'runtime_dependency.child'
        package.child = child
        return child

    importer = Mock(side_effect=import_module)
    monkeypatch.setattr(
        'one_dragon.envs.runtime_compatibility.importlib',
        SimpleNamespace(import_module=importer),
    )

    assert check_manifest_compatible(
        b'import runtime_dependency\n',
        b'from runtime_dependency import child\n',
    ) is True
    assert [call.args[0] for call in importer.call_args_list] == [
        'runtime_dependency',
        'runtime_dependency.child',
    ]


def test_from_import_accepts_cached_submodule_without_parent_attribute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已缓存子模块不要求父包仍保留同名属性，与 Python 的 from 导入一致。"""
    package = ModuleType('manifest_cached_package')
    package.__path__ = []
    child = ModuleType('manifest_cached_package.child')
    monkeypatch.setitem(sys.modules, package.__name__, package)
    monkeypatch.setitem(sys.modules, child.__name__, child)

    from manifest_cached_package import child as imported_child

    assert imported_child is child
    assert not hasattr(package, 'child')
    assert check_manifest_compatible(
        b'import manifest_cached_package\n',
        b'from manifest_cached_package import child\n',
    ) is True


@pytest.mark.parametrize(
    'remote',
    [
        b'import nonexistent_runtime_dependency_20261025\n',
        b'import json.nonexistent_submodule_20261025\n',
        b'from math import nonexistent_symbol_20261025\n',
        b'from json import nonexistent_submodule_20261025\n',
    ],
)
def test_missing_modules_or_symbols_block_update(remote: bytes) -> None:
    """顶层包存在不代表它的子模块或导入名称可用。"""
    assert check_manifest_compatible(b'import sys\n', remote) is False


@pytest.mark.parametrize(
    'error',
    [
        ModuleNotFoundError('依赖未打包'),
        ImportError('扩展模块无法加载'),
        OSError('DLL 加载失败'),
        RuntimeError('依赖初始化失败'),
    ],
)
def test_dependency_loading_errors_block_update(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    """已找到模块但加载失败时仍拦截更新，不向外层抛出异常。"""
    importer = Mock(side_effect=error)
    monkeypatch.setattr(
        'one_dragon.envs.runtime_compatibility.importlib',
        SimpleNamespace(import_module=importer),
    )

    assert check_manifest_compatible(b'import sys\n', b'import dependency\n') is False


@pytest.mark.parametrize(
    ('local', 'remote'),
    [
        (b'import sys\n', b'from json import (\n'),
        (b'import (\n', b'import sys\n'),
        (b'import sys\n', b'\xff\n'),
        (b'import sys\n', b'from . import dependency\n'),
        (b'import sys\n', b'from math import *\n'),
    ],
)
def test_unparseable_or_unsupported_changed_manifests_block_update(
    local: bytes,
    remote: bytes,
) -> None:
    """无法可靠解析变化后的清单时保持原有拦截行为。"""
    assert check_manifest_compatible(local, remote) is False


def test_manifest_code_is_not_executed() -> None:
    """只提取导入要求，不执行远程清单中的语句。"""
    assert check_manifest_compatible(
        b'import sys\n',
        b"raise RuntimeError('must not run')\nimport sys\nimport math\n",
    ) is True


def test_runtime_import_paths_and_loaded_module_are_unchanged() -> None:
    """新增导入检查不重排路径、不替换已加载模块。"""
    search_path = list(sys.path)
    loaded_module = importlib.import_module('one_dragon.version')

    assert check_manifest_compatible(b'import sys\n', b'import sys\nimport math\n') is True
    assert sys.path == search_path
    assert importlib.import_module('one_dragon.version') is loaded_module
