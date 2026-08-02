import os
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

import one_dragon_qt.view.code_interface as code_interface_module
from one_dragon.envs.git_service import GitSyncStatus
from one_dragon_qt.widgets.install_card.base_install_card import InstallRunner
from one_dragon_qt.widgets.install_card.code_install_card import CodeInstallCard


@pytest.mark.parametrize(
    ('status', 'expected_success'),
    [
        (GitSyncStatus.SUCCESS, True),
        (GitSyncStatus.UP_TO_DATE, True),
        (GitSyncStatus.RUNTIME_INCOMPATIBLE, False),
        (GitSyncStatus.BUILTIN_TAG_UNAVAILABLE, False),
        (GitSyncStatus.REMOTE_UNAVAILABLE, False),
        (GitSyncStatus.LOCAL_CHANGES, False),
        (GitSyncStatus.LOCAL_UPDATE_FAILED, False),
        (GitSyncStatus.FAILED, False),
    ],
)
def test_fetch_latest_code_keeps_status_for_display(
    status: GitSyncStatus,
    expected_success: bool,
) -> None:
    def progress_callback(progress: float, message: str) -> None:
        pass

    git_service = SimpleNamespace(
        fetch_latest_code=lambda callback: (status, '同步结果'),
    )
    card = SimpleNamespace(
        ctx=SimpleNamespace(git_service=git_service),
        _last_sync_status=GitSyncStatus.FAILED,
    )

    success, message = CodeInstallCard.fetch_latest_code(card, progress_callback)

    assert success is expected_success
    assert message == '同步结果'
    assert card._last_sync_status is status


def test_install_runner_receives_success_bool_from_code_card() -> None:
    _app = QApplication.instance() or QApplication([])
    received: list[tuple[bool, str]] = []
    git_service = SimpleNamespace(
        fetch_latest_code=lambda callback: (GitSyncStatus.UP_TO_DATE, '当前已是最新版本'),
    )
    card = SimpleNamespace(
        ctx=SimpleNamespace(git_service=git_service),
        _last_sync_status=GitSyncStatus.FAILED,
    )
    runner = InstallRunner(lambda callback: CodeInstallCard.fetch_latest_code(card, callback))
    runner.finished.connect(lambda success, message: received.append((success, message)))

    runner.run()

    assert received == [(True, '当前已是最新版本')]
    assert card._last_sync_status is GitSyncStatus.UP_TO_DATE


@pytest.mark.parametrize(
    ('status', 'expected_message'),
    [
        (GitSyncStatus.SUCCESS, '更新完成，重启后生效'),
        (GitSyncStatus.UP_TO_DATE, '当前已是最新版本'),
        (GitSyncStatus.RUNTIME_INCOMPATIBLE, '新版本需要更新启动器才能使用，请先更新启动器'),
        (GitSyncStatus.BUILTIN_TAG_UNAVAILABLE, '暂时无法获取当前版本所需文件，请稍后重试'),
        (GitSyncStatus.REMOTE_UNAVAILABLE, '暂时无法获取更新，请稍后重试或切换代码源'),
        (GitSyncStatus.LOCAL_CHANGES, '检测到程序文件有改动，未自动更新。可开启“强制更新”后重试'),
        (GitSyncStatus.LOCAL_UPDATE_FAILED, '更新没有完成，请重启后重试；仍然失败时请重新安装'),
        (GitSyncStatus.FAILED, '更新失败，请稍后重试；仍然失败时请查看日志'),
    ],
)
def test_sync_status_uses_user_facing_message(
    status: GitSyncStatus,
    expected_message: str,
) -> None:
    messages: list[str] = []
    card = SimpleNamespace(
        updated=False,
        _last_sync_status=status,
        update_display=lambda icon, message: messages.append(message),
    )

    CodeInstallCard.after_progress_done(
        card,
        status in (GitSyncStatus.SUCCESS, GitSyncStatus.UP_TO_DATE),
        status.value,
    )

    assert messages == [expected_message]
    assert 'tag' not in messages[0]
    assert 'checkout' not in messages[0]
    assert 'reset' not in messages[0]
    assert '安装器' not in messages[0]
    assert card.updated is (status is GitSyncStatus.SUCCESS)


def test_up_to_date_does_not_open_restart_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        code_interface_module,
        'Dialog',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('已是最新时不应弹出重启提示')),
    )
    interface = SimpleNamespace(
        code_card=SimpleNamespace(last_sync_status=GitSyncStatus.UP_TO_DATE),
    )

    code_interface_module.CodeInterface._show_dialog_after_code_updated(interface, True)
