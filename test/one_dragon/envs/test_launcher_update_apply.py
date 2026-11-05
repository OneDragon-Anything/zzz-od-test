"""集成启动器更新：运行中不改 .runtime，新目录落到 .runtime.new。"""

from pathlib import Path

import pytest

import one_dragon.envs.update_service as update_service_module
from one_dragon.envs.update_service import UpdateService
from one_dragon.launcher import runtime_paths


def _service() -> UpdateService:
    """构造只带版本查询的服务实例。"""
    return UpdateService.__new__(UpdateService)


def _make_dir(root: Path, files: dict[str, bytes]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


@pytest.fixture()
def work_dir(tmp_path: Path, monkeypatch) -> Path:
    """把工作目录指向临时目录。"""
    monkeypatch.setattr(
        update_service_module.os_utils, 'get_work_dir', lambda: str(tmp_path)
    )
    return tmp_path


class TestApplyStagedLauncherUpdate:

    def test_stages_new_runtime_without_touching_current(
        self, work_dir: Path
    ) -> None:
        _make_dir(work_dir / '.runtime', {'python.exe': b'old'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_dir(
            work_dir / '.env' / 'launcher_update' / 'runtime' / 'v2',
            {
                'OneDragon-RuntimeLauncher.exe': b'new exe',
                '.runtime/python.exe': b'new',
            },
        )

        _service().apply_staged_launcher_update('runtime', staging)

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'new exe'
        # 当前进程还在用的运行时目录保持原样，等下次启动替换
        assert (work_dir / '.runtime' / 'python.exe').read_bytes() == b'old'
        assert (work_dir / runtime_paths.RUNTIME_DIR_NEW / 'python.exe').read_bytes() == b'new'
        assert not staging.exists()

    def test_identical_runtime_is_not_staged(self, work_dir: Path) -> None:
        """版本号变了但运行时文件一致时不做整目录替换。"""
        _make_dir(work_dir / '.runtime', {'python.exe': b'same'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_dir(
            work_dir / '.env' / 'launcher_update' / 'runtime' / 'v2',
            {
                'OneDragon-RuntimeLauncher.exe': b'new exe',
                '.runtime/python.exe': b'same',
            },
        )

        _service().apply_staged_launcher_update('runtime', staging)

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'new exe'
        assert not (work_dir / runtime_paths.RUNTIME_DIR_NEW).exists()

    def test_missing_staged_runtime_rejects_package(self, work_dir: Path) -> None:
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_dir(
            work_dir / '.env' / 'launcher_update' / 'runtime' / 'v2',
            {'OneDragon-RuntimeLauncher.exe': b'new exe'},
        )

        with pytest.raises(RuntimeError, match='运行环境缺失'):
            _service().apply_staged_launcher_update('runtime', staging)

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'old exe'

    def test_exe_replaced_with_backup_kept_for_cleanup(
        self, work_dir: Path
    ) -> None:
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_dir(
            work_dir / '.env' / 'launcher_update' / 'runtime' / 'v2',
            {
                'OneDragon-RuntimeLauncher.exe': b'new exe',
                '.runtime/python.exe': b'new',
            },
        )

        _service().apply_staged_launcher_update('runtime', staging)

        backup = work_dir / 'OneDragon-RuntimeLauncher.bak.exe'
        assert backup.read_bytes() == b'old exe'

    def test_original_launcher_cleans_backup_right_away(self, work_dir: Path) -> None:
        """原始启动器不受运行中占用影响，备份当场删除。"""
        (work_dir / 'OneDragon-Launcher.exe').write_bytes(b'old exe')
        staging = _make_dir(
            work_dir / '.env' / 'launcher_update' / 'launcher' / 'v2',
            {'OneDragon-Launcher.exe': b'new exe'},
        )

        _service().apply_staged_launcher_update('launcher', staging)

        assert (work_dir / 'OneDragon-Launcher.exe').read_bytes() == b'new exe'
        assert not (work_dir / 'OneDragon-Launcher.bak.exe').exists()
