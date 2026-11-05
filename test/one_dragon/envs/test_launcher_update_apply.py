"""集成启动器更新：exe 与运行时一起在进程退出后替换。"""

from pathlib import Path

import pytest

import one_dragon.envs.update_service as update_service_module
from one_dragon.envs.update_service import UpdateService
from one_dragon.launcher import runtime_paths


def _service() -> UpdateService:
    """构造只带版本查询的服务实例。"""
    service = UpdateService.__new__(UpdateService)
    service._launcher_version_cache = {}
    return service


def _make_dir(root: Path, files: dict[str, bytes]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


@pytest.fixture(autouse=True)
def popen_calls(monkeypatch) -> list[list[str]]:
    """拦掉后台替换脚本，测试里只记录调用。"""
    calls: list[list[str]] = []

    def fake_popen(args, **kwargs):
        calls.append(list(args))

    monkeypatch.setattr(runtime_paths.subprocess, 'Popen', fake_popen)
    return calls


@pytest.fixture(autouse=True)
def exe_version(monkeypatch) -> dict[str, str]:
    """当前启动器版本由测试控制，别真的去读 exe。"""
    state = {'value': ''}
    monkeypatch.setattr(
        update_service_module.app_utils,
        'get_exe_version',
        lambda _path: state['value'],
    )
    return state


@pytest.fixture()
def work_dir(tmp_path: Path, monkeypatch) -> Path:
    """把工作目录指向临时目录。"""
    monkeypatch.setattr(
        update_service_module.os_utils, 'get_work_dir', lambda: str(tmp_path)
    )
    return tmp_path


def _make_runtime_package(work_dir: Path, exe: bytes, runtime_file: bytes) -> Path:
    """造一个集成启动器更新包。"""
    return _make_dir(
        work_dir / '.env' / 'launcher_update' / 'runtime' / 'v2',
        {
            'OneDragon-RuntimeLauncher.exe': exe,
            '.runtime/python.exe': runtime_file,
        },
    )


class TestApplyStagedLauncherUpdate:

    def test_changed_runtime_defers_exe_and_runtime(
        self, work_dir: Path, popen_calls: list[list[str]]
    ) -> None:
        """运行时变了：exe 和运行时都不能当场换，否则新 exe 会用旧运行时启动。"""
        _make_dir(work_dir / '.runtime', {'python.exe': b'old'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_runtime_package(work_dir, b'new exe', b'new')

        _service().apply_staged_launcher_update('runtime', staging)

        # 当前进程用的 exe 和运行时都保持原样
        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'old exe'
        assert (work_dir / '.runtime' / 'python.exe').read_bytes() == b'old'
        # 新文件暂存，等退出后一起换
        assert (work_dir / '.runtime.new' / 'python.exe').read_bytes() == b'new'
        assert (work_dir / 'OneDragon-RuntimeLauncher.exe.new').read_bytes() == b'new exe'
        assert len(popen_calls) == 1
        assert popen_calls[0][2] == 'OneDragon-RuntimeLauncher.exe'
        assert not staging.exists()

    def test_identical_runtime_still_defers_exe(
        self, work_dir: Path, popen_calls: list[list[str]]
    ) -> None:
        """运行时一致时只换 exe，但 exe 仍在退出后换，不覆盖正在运行的文件。"""
        _make_dir(work_dir / '.runtime', {'python.exe': b'same'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_runtime_package(work_dir, b'new exe', b'same')

        _service().apply_staged_launcher_update('runtime', staging)

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'old exe'
        assert not (work_dir / runtime_paths.RUNTIME_DIR_NEW).exists()
        assert (work_dir / 'OneDragon-RuntimeLauncher.exe.new').read_bytes() == b'new exe'
        assert len(popen_calls) == 1
        assert popen_calls[0][2] == 'OneDragon-RuntimeLauncher.exe'

    def test_changed_runtime_creates_no_exe_backup(
        self, work_dir: Path
    ) -> None:
        """延后替换不需要 exe 备份：exe 由脚本用复制方式换掉。"""
        _make_dir(work_dir / '.runtime', {'python.exe': b'old'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_runtime_package(work_dir, b'new exe', b'new')

        _service().apply_staged_launcher_update('runtime', staging)

        assert not (work_dir / 'OneDragon-RuntimeLauncher.bak.exe').exists()

    def test_missing_staged_runtime_rejects_package(self, work_dir: Path) -> None:
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_dir(
            work_dir / '.env' / 'launcher_update' / 'runtime' / 'v2',
            {'OneDragon-RuntimeLauncher.exe': b'new exe'},
        )

        with pytest.raises(RuntimeError, match='运行环境缺失'):
            _service().apply_staged_launcher_update('runtime', staging)

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'old exe'

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


class TestRestoreInterruptedLauncherUpdate:

    def test_leftover_new_exe_kept_when_exe_ok(
        self, work_dir: Path, popen_calls: list[list[str]]
    ) -> None:
        """上次替换脚本没跑完、exe 还在：保留 .new，等启动后再安排替换。"""
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'current exe')
        _make_dir(work_dir / '.runtime', {'python.exe': b'runtime'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe.new').write_bytes(b'staged exe')

        _service().restore_interrupted_launcher_update()

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe.new').read_bytes() == b'staged exe'
        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'current exe'

    def test_new_exe_used_when_exe_missing(
        self, work_dir: Path, popen_calls: list[list[str]]
    ) -> None:
        """exe 不在但 .new 在：先补回 exe，保证程序还能启动。"""
        _make_dir(work_dir / '.runtime', {'python.exe': b'runtime'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe.new').write_bytes(b'staged exe')

        _service().restore_interrupted_launcher_update()

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'staged exe'
        assert not (work_dir / 'OneDragon-RuntimeLauncher.exe.new').exists()


class TestLauncherVersionCache:

    def test_cache_cleared_after_update(
        self, work_dir: Path, popen_calls: list[list[str]]
    ) -> None:
        """更新完成后清版本缓存，卡片才能读到新版本。"""
        service = _service()
        service._launcher_version_cache = {'runtime': ('v1.0', 'v1.1', 'v1.1')}
        _make_dir(work_dir / '.runtime', {'python.exe': b'same'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        staging = _make_runtime_package(work_dir, b'new exe', b'same')

        service.apply_staged_launcher_update('runtime', staging)

        assert service._launcher_version_cache == {}


class TestIsLauncherInstalled:

    def test_empty_file_is_not_installed(self, work_dir: Path) -> None:
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'')

        assert UpdateService.is_launcher_installed('runtime') is False

    def test_non_empty_file_is_installed(self, work_dir: Path) -> None:
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'x')

        assert UpdateService.is_launcher_installed('runtime') is True


class TestDowngradeGuard:

    def _prepare(self, work_dir: Path, staging_name: str) -> Path:
        _make_dir(work_dir / '.runtime', {'python.exe': b'same'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        return _make_dir(
            work_dir / '.env' / 'launcher_update' / 'runtime' / staging_name,
            {
                'OneDragon-RuntimeLauncher.exe': b'new exe',
                '.runtime/python.exe': b'same',
            },
        )

    def test_rejects_downgrade(
        self, work_dir: Path, exe_version: dict[str, str]
    ) -> None:
        """启动时的更新也会走这里，降级包直接拒绝。"""
        exe_version['value'] = 'v2.6.0'
        staging = self._prepare(work_dir, 'v2.5.1')

        with pytest.raises(RuntimeError, match='不允许降级安装启动器'):
            _service().apply_staged_launcher_update('runtime', staging)

        assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'old exe'

    def test_allows_upgrade(
        self, work_dir: Path, exe_version: dict[str, str]
    ) -> None:
        exe_version['value'] = 'v2.5.1'
        staging = self._prepare(work_dir, 'v2.6.0')

        _service().apply_staged_launcher_update('runtime', staging)

        # exe 延后到退出后替换，这里只确认暂存成功
        assert (work_dir / 'OneDragon-RuntimeLauncher.exe.new').read_bytes() == b'new exe'


class TestUnparseableVersion:

    def _prepare(self, work_dir: Path) -> Path:
        _make_dir(work_dir / '.runtime', {'python.exe': b'same'})
        (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old exe')
        return _make_runtime_package(work_dir, b'new exe', b'same')

    def test_rejects_unparseable_current_version(
        self, work_dir: Path, exe_version: dict[str, str]
    ) -> None:
        """版本读出来但解析不了时不能放行，否则降级判断会失效。"""
        from one_dragon.envs.update_service import is_version_parseable

        assert is_version_parseable('unknown') is False
        exe_version['value'] = 'unknown'
        staging = self._prepare(work_dir)

        with pytest.raises(RuntimeError, match='无法识别当前启动器版本'):
            _service().apply_staged_launcher_update('runtime', staging)
