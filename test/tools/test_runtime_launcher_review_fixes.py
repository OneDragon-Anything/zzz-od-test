from __future__ import annotations

import inspect
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.envs.git_service import GitSyncStatus
from one_dragon.envs.recovery_repair_service import (
    RecoveryRepairEvent,
    RecoveryRepairService,
    RecoveryRepairStage,
)
from one_dragon.envs.update_service import UpdateService
from one_dragon_qt.view.recovery_repair_interface import RecoveryRepairInterface
from one_dragon_qt.view.resource_management_interface import (
    ResourceManagementInterface,
)


def test_resource_management_interface_has_no_recovery_mode() -> None:
    parameters = inspect.signature(ResourceManagementInterface.__init__).parameters

    assert 'recovery_mode' not in parameters
    assert 'launcher_version' not in parameters
    assert 'recovery_adapter' not in parameters


@pytest.mark.parametrize('active', [False, True])
def test_recovery_interface_only_tracks_repair_task(active: bool) -> None:
    adapter = SimpleNamespace(is_active=lambda: active)
    interface = SimpleNamespace(recovery_adapter=adapter)

    assert RecoveryRepairInterface.has_recovery_active_task(interface) is active


def test_cancel_after_git_checkout_starts_still_applies_staged_launcher(
    tmp_path: Path,
) -> None:
    events: list[RecoveryRepairEvent] = []
    applied: list[Path] = []
    service: RecoveryRepairService
    staging_dir = tmp_path / 'staging'

    class GitServiceStub:
        @staticmethod
        def fetch_tag_code(
            _tag: str,
            progress_callback=None,
            force: bool = False,
            before_checkout=None,
        ) -> tuple[GitSyncStatus, str]:
            assert before_checkout is not None
            assert before_checkout() is False
            service.cancel()
            return GitSyncStatus.SUCCESS, 'ok'

    class UpdateServiceStub:
        @staticmethod
        def check_launcher_asset(
            _launcher_type: str,
            _tag: str,
        ) -> dict[str, str]:
            return {'github': 'https://example.com/runtime.zip'}

        @staticmethod
        def get_launcher_staging_dir(_launcher_type: str, _tag: str) -> Path:
            return staging_dir

        @staticmethod
        def get_launcher_download_param(
            _launcher_type: str,
            _tag: str,
            staging: bool,
            download_urls: dict[str, str],
        ) -> CommonDownloaderParam:
            return CommonDownloaderParam(
                str(staging_dir),
                'runtime.zip',
                download_urls,
            )

        @staticmethod
        def validate_staged_launcher(_launcher_type: str, _staging_dir: Path) -> None:
            pass

        @staticmethod
        def apply_staged_launcher_update(
            _launcher_type: str,
            selected_staging_dir: Path,
        ) -> None:
            applied.append(selected_staging_dir)

    service = RecoveryRepairService(
        SimpleNamespace(
            git_service=GitServiceStub(),
            update_service=UpdateServiceStub(),
        ),
        event_callback=events.append,
    )
    service._worker = threading.current_thread()
    service._target = 'v1.2.3'
    service._get_workspace_snapshot = lambda: ()
    service._download = lambda _param: None
    service._run()

    assert applied == [staging_dir]
    assert any(event.stage is RecoveryRepairStage.SUCCEEDED for event in events)
    assert not any(event.stage is RecoveryRepairStage.CANCELLED for event in events)


def test_cleanup_failure_keeps_new_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from one_dragon.envs.launcher_update_transaction import LauncherUpdateTransaction

    work_dir = tmp_path / 'work'
    staging_dir = tmp_path / 'staging'
    work_dir.mkdir()
    (staging_dir / 'OneDragon-RuntimeLauncher.exe').parent.mkdir(parents=True)
    (staging_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'new')
    (staging_dir / '.runtime' / 'builtin_src' / 'src').mkdir(parents=True)
    (staging_dir / '.runtime' / 'builtin_src' / 'manifest.json').write_text(
        '{}',
        encoding='utf-8',
    )
    (work_dir / 'OneDragon-RuntimeLauncher.exe').write_bytes(b'old')
    (work_dir / '.runtime').mkdir()
    monkeypatch.setattr(
        'one_dragon.envs.update_service.os_utils.get_work_dir',
        lambda: work_dir,
    )
    monkeypatch.setattr(
        'one_dragon.envs.launcher_update_transaction.os_utils.get_work_dir',
        lambda: work_dir,
    )

    service = UpdateService.__new__(UpdateService)
    service._launcher_transaction = LauncherUpdateTransaction()

    def fail_cleanup(_launcher_type: str, success: bool) -> None:
        assert success is True
        service._launcher_transaction.mark_cleanup('runtime')
        raise OSError('cleanup failed')

    service.finish_launcher_update = fail_cleanup

    with pytest.raises(OSError, match='cleanup failed'):
        service.apply_staged_launcher_update('runtime', staging_dir)

    assert (work_dir / 'OneDragon-RuntimeLauncher.exe').read_bytes() == b'new'
    assert (work_dir / '.runtime.bak').is_dir()
    assert (work_dir / '.runtime.update.pending').read_text(
        encoding='utf-8'
    ) == 'runtime:cleanup'


def test_validate_staged_runtime_launcher_is_public(tmp_path: Path) -> None:
    service = UpdateService.__new__(UpdateService)
    staging_dir = tmp_path / 'staging'
    executable = staging_dir / 'OneDragon-RuntimeLauncher.exe'
    builtin_root = staging_dir / '.runtime' / 'builtin_src'
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b'executable')
    (builtin_root / 'src').mkdir(parents=True)
    manifest = builtin_root / 'manifest.json'
    manifest.write_text('{}', encoding='utf-8')

    service.validate_staged_launcher('runtime', staging_dir)
    manifest.unlink()

    with pytest.raises(RuntimeError, match='缺少内置清单'):
        service.validate_staged_launcher('runtime', staging_dir)
