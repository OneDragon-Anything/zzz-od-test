# ruff: noqa: E402

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

import one_dragon

PROJECT_ROOT = Path(one_dragon.__file__).resolve().parents[2]
DEPLOY_DIR = PROJECT_ROOT / 'deploy'
SRC_DIR = PROJECT_ROOT / 'src'
CI_TOOLS_DIR = PROJECT_ROOT / 'tools' / 'ci'
for path in (DEPLOY_DIR, SRC_DIR, CI_TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from generate_builtin_source import generate_builtin_source
from prepare_release_assets import _validate_runtime_launcher_dir

from one_dragon.launcher.runtime_launcher_bootstrap.launcher import (
    LauncherOptions,
    RuntimeLauncherSupervisor,
    RuntimePaths,
)
from one_dragon.launcher.runtime_launcher_bootstrap.profile import (
    RuntimeLauncherProfile,
)
from zzz_od.win_exe.runtime_launcher_profile import ZRuntimeLauncherProfile


class StubRuntimeLauncherProfile(RuntimeLauncherProfile):
    """测试使用的项目配置。"""

    def __init__(
        self,
        external_files: tuple[str, ...] = ('project/runtime_entry.py',),
        builtin_files: tuple[str, ...] = ('project/recovery_entry.py',),
    ) -> None:
        self._external_files: tuple[str, ...] = external_files
        self._builtin_files: tuple[str, ...] = builtin_files

    @property
    def application_name(self) -> str:
        return '测试应用启动器'

    @property
    def runtime_entry_module(self) -> str:
        return 'project.runtime_entry'

    @property
    def recovery_entry_module(self) -> str:
        return 'project.recovery_entry'

    @property
    def required_external_files(self) -> tuple[str, ...]:
        return self._external_files

    @property
    def required_builtin_files(self) -> tuple[str, ...]:
        return self._builtin_files


def _make_paths(root: Path) -> RuntimePaths:
    builtin_root = root / '.runtime' / 'builtin_src'
    return RuntimePaths(
        install_root=root,
        external_src=root / 'src',
        builtin_src=builtin_root / 'src',
        builtin_manifest=builtin_root / 'manifest.json',
        failure_log=root / '.log' / 'runtime_launcher_startup_error.log',
    )


def test_bootstrap_is_nested_under_launcher_and_has_no_project_dependency() -> None:
    old_package = SRC_DIR / 'one_dragon' / 'runtime_launcher_bootstrap'
    package = SRC_DIR / 'one_dragon' / 'launcher' / 'runtime_launcher_bootstrap'

    assert not list(old_package.glob('*.py'))
    assert (package / 'launcher.py').is_file()
    source = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted(package.glob('*.py'))
    )
    assert 'zzz_od' not in source
    assert '绝区零' not in source


def test_runtime_launcher_profile_is_abstract() -> None:
    with pytest.raises(TypeError):
        RuntimeLauncherProfile()


def test_project_profile_owns_runtime_entries_and_required_files() -> None:
    profile = ZRuntimeLauncherProfile()

    assert profile.runtime_entry_module == 'zzz_od.win_exe.runtime_launcher'
    assert profile.recovery_entry_module == 'zzz_od.win_exe.recovery_app'
    assert 'zzz_od/gui/app.py' in profile.required_external_files
    assert 'zzz_od/win_exe/recovery_app.py' in profile.required_builtin_files
    assert profile.frozen_import_modules == (
        'one_dragon.envs.recovery_repair_service',
    )


def test_activate_source_updates_all_entry_parent_packages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    profile = ZRuntimeLauncherProfile()
    package_names = (
        'one_dragon',
        'one_dragon.launcher',
        'zzz_od',
        'zzz_od.win_exe',
    )
    frozen_root = tmp_path / 'frozen'
    packages: dict[str, ModuleType] = {}
    for package_name in package_names:
        selected_package_root = paths.external_src / Path(*package_name.split('.'))
        selected_package_root.mkdir(parents=True, exist_ok=True)
        package = ModuleType(package_name)
        package.__path__ = [str(frozen_root / Path(*package_name.split('.')))]
        packages[package_name] = package
        monkeypatch.setitem(sys.modules, package_name, package)
    runtime_entry = paths.external_src / 'zzz_od' / 'win_exe' / 'runtime_launcher.py'
    runtime_entry.write_text("SOURCE = 'external'\n", encoding='utf-8')
    monkeypatch.delitem(sys.modules, profile.runtime_entry_module, raising=False)
    supervisor = RuntimeLauncherSupervisor(paths, 'v1.2.3', profile)

    supervisor._activate_source(paths.external_src, 'external')

    for package_name, package in packages.items():
        expected_root = paths.external_src / Path(*package_name.split('.'))
        assert package.__path__[0] == str(frozen_root / Path(*package_name.split('.')))
        assert package.__path__[-1] == str(expected_root)
    runtime_module = importlib.import_module(profile.runtime_entry_module)
    assert runtime_module.SOURCE == 'external'
    sys.modules.pop(profile.runtime_entry_module, None)


def test_external_validation_uses_project_profile(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    profile = StubRuntimeLauncherProfile()
    required_file = paths.external_src / profile.required_external_files[0]
    required_file.parent.mkdir(parents=True)
    required_file.write_text('entry\n', encoding='utf-8')
    supervisor = RuntimeLauncherSupervisor(paths, 'v1.2.3', profile)

    supervisor._validate_external_source()
    required_file.unlink()

    with pytest.raises(FileNotFoundError, match='project/runtime_entry.py'):
        supervisor._validate_external_source()


def test_builtin_manifest_uses_project_profile(tmp_path: Path) -> None:
    source_root = tmp_path / 'source'
    output_root = tmp_path / 'install' / '.runtime' / 'builtin_src'
    profile = StubRuntimeLauncherProfile()
    required_file = source_root / profile.required_builtin_files[0]
    required_file.parent.mkdir(parents=True)
    required_file.write_text('entry\n', encoding='utf-8')

    manifest_path = generate_builtin_source(
        source_root,
        output_root,
        'v1.2.3',
        profile=profile,
    )
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    paths = _make_paths(tmp_path / 'install')
    supervisor = RuntimeLauncherSupervisor(paths, 'v1.2.3', profile)

    assert manifest['required_files'] == list(profile.required_builtin_files)
    supervisor._validate_builtin_source()


def test_release_validation_uses_project_profile(tmp_path: Path) -> None:
    runtime_root = tmp_path / 'runtime-launcher'
    profile = StubRuntimeLauncherProfile()
    executable = runtime_root / 'OneDragon-RuntimeLauncher.exe'
    manifest = runtime_root / '.runtime' / 'builtin_src' / 'manifest.json'
    external_file = runtime_root / 'src' / profile.required_external_files[0]
    builtin_file = (
        runtime_root
        / '.runtime'
        / 'builtin_src'
        / 'src'
        / profile.required_builtin_files[0]
    )
    for path in (executable, external_file, builtin_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'content')
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({'release_version': 'v1.2.3'}),
        encoding='utf-8',
    )

    _validate_runtime_launcher_dir(runtime_root, 'v1.2.3', profile)
    builtin_file.unlink()

    with pytest.raises(SystemExit, match='build is incomplete'):
        _validate_runtime_launcher_dir(runtime_root, 'v1.2.3', profile)


def test_exit_after_ready_reports_runtime_failure_without_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown: list[tuple[str, str]] = []
    recoveries: list[str] = []
    supervisor = RuntimeLauncherSupervisor.__new__(RuntimeLauncherSupervisor)
    supervisor.paths = RuntimePaths(
        install_root=tmp_path,
        external_src=tmp_path / 'src',
        builtin_src=tmp_path / 'builtin' / 'src',
        builtin_manifest=tmp_path / 'builtin' / 'manifest.json',
        failure_log=tmp_path / 'error.log',
    )
    supervisor.version = 'v1.2.3'
    supervisor.profile = StubRuntimeLauncherProfile()
    supervisor.ready = False
    supervisor._show_fatal_error = lambda title, detail: shown.append((title, detail))
    supervisor._start_recovery_process = lambda detail: recoveries.append(detail) or 7

    class EntryStub:
        @staticmethod
        def run_onedragon(_args: list[str], on_ready) -> int:
            on_ready()
            raise SystemExit(3)

    monkeypatch.setattr(
        'one_dragon.launcher.runtime_launcher_bootstrap.launcher.importlib.import_module',
        lambda _name: EntryStub,
    )
    monkeypatch.setattr(supervisor, '_validate_external_source', lambda: None)
    monkeypatch.setattr(supervisor, '_activate_source', lambda *_args: None)
    monkeypatch.setattr(supervisor.profile, 'sync_source', lambda _version: False)

    result = supervisor.run_normal(
        LauncherOptions(
            show_version=False,
            onedragon=True,
            close_game=False,
            shutdown=None,
            instance='1',
            recovery=False,
        )
    )

    assert result == 1
    assert recoveries == []
    assert shown and shown[0][0] == '运行失败'


def test_runtime_launcher_spec_uses_project_bootstrap_without_json() -> None:
    spec = (DEPLOY_DIR / 'OneDragon-RuntimeLauncher.spec').read_text(
        encoding='utf-8'
    )

    assert "'zzz_od' / 'win_exe' / 'runtime_launcher_bootstrap.py'" in spec
    assert '*project_profile.frozen_import_modules' in spec
    assert 'runtime_launcher_profile.json' not in spec
    assert "'one_dragon' / 'runtime_launcher_bootstrap'" not in spec
