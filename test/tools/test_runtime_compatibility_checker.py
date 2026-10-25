import importlib.util
import struct
import zlib
from pathlib import Path
from types import ModuleType

import pytest


def _load_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[3]
        / 'tools'
        / 'ci'
        / 'check_runtime_compatibility.py'
    )
    spec = importlib.util.spec_from_file_location('check_runtime_compatibility', script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


def _entry(name: str, type_code: str, data: bytes, compressed: bool = False) -> bytes:
    payload = zlib.compress(data) if compressed else data
    raw_name = name.encode('utf-8') + b'\0'
    entry_length = 18 + len(raw_name)
    return struct.pack(
        '!IIIIBB',
        entry_length,
        0,
        len(payload),
        len(data),
        int(compressed),
        ord(type_code),
    ) + raw_name


def _executable(entries: list[tuple[str, str, bytes]]) -> bytes:
    payload = b''.join(data for _name, _type_code, data in entries)
    table = b''.join(_entry(name, type_code, data) for name, type_code, data in entries)
    package_length = len(payload) + len(table) + 88
    cookie = struct.pack('!8sIIii', MODULE.ARCHIVE_MAGIC, package_length, len(payload), len(table), 311)
    cookie += b'python311.dll'.ljust(64, b'\0')
    return payload + table + cookie


def test_archive_entries_reads_compressed_entry(tmp_path: Path) -> None:
    executable = _executable([('pyimod01_archive', 'm', b'archive-code')])
    destination = tmp_path / 'importer.pyc'

    entries = MODULE._archive_entries(executable)
    destination.write_bytes(MODULE._entry_bytes(executable, entries[0]))

    assert entries[0][0] == 'pyimod01_archive'
    assert destination.read_bytes() == b'archive-code'


def test_extract_pyz_rejects_invalid_archive(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match='PyInstaller 归档'):
        MODULE._extract_pyz(b'not-a-runtime', tmp_path / 'PYZ.pyz')


def test_target_manifest_uses_project_config(tmp_path: Path) -> None:
    config_dir = tmp_path / 'config'
    config_dir.mkdir()
    (config_dir / 'project.yml').write_text('manifest_path: deploy/module_manifest.py\n', encoding='utf-8')
    manifest = tmp_path / 'deploy' / 'module_manifest.py'
    manifest.parent.mkdir()
    manifest.write_bytes(b'import sys\n')

    assert MODULE._target_manifest(tmp_path) == b'import sys\n'


def test_target_manifest_rejects_path_outside_repository(tmp_path: Path) -> None:
    config_dir = tmp_path / 'config'
    config_dir.mkdir()
    (config_dir / 'project.yml').write_text('manifest_path: ../module_manifest.py\n', encoding='utf-8')

    with pytest.raises(RuntimeError, match='模块清单不存在'):
        MODULE._target_manifest(tmp_path)
