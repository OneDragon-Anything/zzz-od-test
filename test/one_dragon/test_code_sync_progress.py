from types import SimpleNamespace

import pytest

import one_dragon.base.operation.one_dragon_env_context as env_context_module
import one_dragon.devtools.python_launcher as python_launcher
import one_dragon.envs.git_service as git_service_module
import one_dragon.utils.i18_utils as i18_utils_module
from one_dragon.launcher.runtime_launcher import RuntimeLauncher


def test_git_service_transfer_progress_limits_transfer_messages(monkeypatch) -> None:
    messages: list[tuple[float, str]] = []
    callback = git_service_module._FetchProgressRemoteCallbacks(
        lambda progress, message: messages.append((progress, message)),
        timeout=None,
    )
    timestamps = iter([0.0, 0.1, 0.4])
    monkeypatch.setattr(git_service_module.time, 'monotonic', lambda: next(timestamps))

    callback.transfer_progress(SimpleNamespace(total_objects=10, received_objects=1, received_bytes=0))
    callback.transfer_progress(SimpleNamespace(total_objects=10, received_objects=2, received_bytes=0))
    callback.transfer_progress(SimpleNamespace(total_objects=10, received_objects=3, received_bytes=0))

    assert messages == [
        (0.1, '拉取对象 1/10 (10%)'),
        (0.3, '拉取对象 3/10 (30%)'),
    ]


def test_git_service_transfer_progress_always_shows_final_100_percent(monkeypatch) -> None:
    messages: list[tuple[float, str]] = []
    callback = git_service_module._FetchProgressRemoteCallbacks(
        lambda progress, message: messages.append((progress, message)),
        timeout=None,
    )
    timestamps = iter([0.0, 0.1])
    monkeypatch.setattr(git_service_module.time, 'monotonic', lambda: next(timestamps))

    callback.transfer_progress(SimpleNamespace(total_objects=10, received_objects=1, received_bytes=0))
    callback.transfer_progress(SimpleNamespace(total_objects=10, received_objects=10, received_bytes=0))

    assert messages == [
        (0.1, '拉取对象 1/10 (10%)'),
        (1.0, '拉取对象 10/10 (100%), done.'),
    ]


def test_python_launcher_fetch_latest_code_passes_progress_callback(
    monkeypatch,
) -> None:
    messages: list[tuple[str, str]] = []

    class FakeGitService:

        def __init__(self) -> None:
            self.progress_callback = None

        def fetch_latest_code(self, progress_callback=None):
            self.progress_callback = progress_callback
            progress_callback(0.421, '拉取对象 3/10 (30%)')
            progress_callback(0.500, '检查运行环境兼容性')
            return (
                git_service_module.GitSyncStatus.SUCCESS,
                git_service_module.GitSyncStatus.SUCCESS.value,
            )

    git_service = FakeGitService()
    ctx = SimpleNamespace(
        env_config=SimpleNamespace(auto_update_code=True),
        git_service=git_service,
    )

    monkeypatch.setattr(
        python_launcher,
        'print_message',
        lambda message, level='INFO', flush=False: messages.append((level, message)),
    )

    python_launcher.fetch_latest_code(ctx)

    assert git_service.progress_callback is not None
    assert ('INFO', '拉取对象 3/10 (30%)') in messages
    assert ('INFO', '检查运行环境兼容性') in messages
    assert ('PASS', '更新完成') in messages


def test_python_launcher_fetch_latest_code_silences_framework_console_log(
    monkeypatch,
) -> None:
    configured: list[tuple[object, str | None, bool, bool]] = []

    class FakeGitService:

        def fetch_latest_code(self, progress_callback=None):
            progress_callback(0.500, '检查运行环境兼容性')
            return (
                git_service_module.GitSyncStatus.SUCCESS,
                git_service_module.GitSyncStatus.SUCCESS.value,
            )

    messages: list[tuple[str, str]] = []
    ctx = SimpleNamespace(
        env_config=SimpleNamespace(auto_update_code=True),
        git_service=FakeGitService(),
    )

    def _fake_configure_logger(logger, config):
        configured.append(
            (
                logger,
                config.log_file_path,
                config.add_console_handler,
                config.propagate,
            )
        )
        return logger

    monkeypatch.setattr(
        python_launcher,
        'configure_logger',
        _fake_configure_logger,
    )
    monkeypatch.setattr(
        python_launcher,
        'print_message',
        lambda message, level='INFO', flush=False: messages.append((level, message)),
    )

    python_launcher.fetch_latest_code(ctx)

    assert configured
    assert configured[0][0] is python_launcher.framework_log
    assert configured[0][1] is not None
    assert configured[0][2] is False
    assert configured[0][3] is False
    assert ('INFO', '检查运行环境兼容性') in messages


@pytest.mark.parametrize(
    ('status', 'expected_level', 'expected_message'),
    [
        (git_service_module.GitSyncStatus.SUCCESS, 'PASS', '更新完成'),
        (git_service_module.GitSyncStatus.UP_TO_DATE, 'PASS', '当前已是最新版本'),
        (
            git_service_module.GitSyncStatus.RUNTIME_INCOMPATIBLE,
            'WARNING',
            '新版本需要更新启动器才能使用，继续使用当前版本',
        ),
        (
            git_service_module.GitSyncStatus.BUILTIN_TAG_UNAVAILABLE,
            'WARNING',
            '暂时无法获取当前版本所需文件，继续使用内置版本',
        ),
        (
            git_service_module.GitSyncStatus.REMOTE_UNAVAILABLE,
            'WARNING',
            '暂时无法获取更新，继续使用当前版本',
        ),
        (
            git_service_module.GitSyncStatus.LOCAL_CHANGES,
            'WARNING',
            '检测到程序文件有改动，未自动更新，继续使用当前版本',
        ),
        (
            git_service_module.GitSyncStatus.LOCAL_UPDATE_FAILED,
            'ERROR',
            '更新没有完成，请重新运行启动器；仍然失败时请重新安装',
        ),
        (git_service_module.GitSyncStatus.FAILED, 'ERROR', '更新失败，请查看日志后重试'),
    ],
)
def test_python_launcher_uses_status_specific_result_message(
    monkeypatch: pytest.MonkeyPatch,
    status: git_service_module.GitSyncStatus,
    expected_level: str,
    expected_message: str,
) -> None:
    class FakeGitService:
        def fetch_latest_code(self, progress_callback=None):
            return status, status.value

    messages: list[tuple[str, str]] = []
    ctx = SimpleNamespace(
        env_config=SimpleNamespace(auto_update_code=True),
        git_service=FakeGitService(),
    )
    monkeypatch.setattr(python_launcher, '_configure_runtime_logger', lambda: None)
    monkeypatch.setattr(
        python_launcher,
        'print_message',
        lambda message, level='INFO', flush=False: messages.append((level, message)),
    )

    python_launcher.fetch_latest_code(ctx)

    assert messages[-1] == (expected_level, expected_message)


def test_python_launcher_progress_callback_passes_stage_messages_through() -> None:
    messages: list[tuple[str, str, bool]] = []

    callback = python_launcher.create_git_progress_callback()
    original_print_message = python_launcher.print_message
    python_launcher.print_message = lambda message, level='INFO', flush=False: messages.append((level, message, flush))
    try:
        callback(0.2, '获取远程代码')
        callback(0.5, '检查工作区状态')
        callback(0.3, '拉取对象 3/10 (30%)')
        callback(1.0, '拉取对象 10/10 (100%), done.')
    finally:
        python_launcher.print_message = original_print_message

    assert messages == [
        ('INFO', '获取远程代码', False),
        ('INFO', '检查工作区状态', False),
        ('INFO', '拉取对象 3/10 (30%)', True),
        ('INFO', '拉取对象 10/10 (100%), done.', False),
    ]


def test_runtime_launcher_sync_code_uses_framework_log(monkeypatch) -> None:
    messages: list[str] = []

    class FakeEnvConfig:
        auto_update_code = True

    class FakeGitService:
        instances: list['FakeGitService'] = []

        def __init__(self) -> None:
            self.progress_callback = None
            FakeGitService.instances.append(self)

        def is_initial_checkout_pending(self) -> bool:
            return False

        def fetch_latest_code(self, progress_callback=None, initial_tag=None):
            self.progress_callback = progress_callback
            progress_callback(0.3, '处理增量 3/10 (30%)')
            progress_callback(1.0, '处理增量 10/10 (100%), done.')
            return (
                git_service_module.GitSyncStatus.SUCCESS,
                git_service_module.GitSyncStatus.SUCCESS.value,
            )

    print_calls: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        env_context_module,
        'OneDragonEnvContext',
        lambda: SimpleNamespace(env_config=FakeEnvConfig(), git_service=FakeGitService()),
    )
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', lambda message: messages.append(message))
    monkeypatch.setattr(
        'builtins.print',
        lambda message, end='\n', flush=False: print_calls.append((message, end, flush)),
    )

    launcher = RuntimeLauncher('test', '1.0.0')
    launcher._sync_code()

    assert len(FakeGitService.instances) == 1
    assert FakeGitService.instances[0].progress_callback is not None
    assert '正在检查代码更新...' in messages
    assert '处理增量 3/10 (30%)' not in messages
    assert '处理增量 10/10 (100%), done.' in messages
    assert print_calls[0] == ('处理增量 3/10 (30%)', '\r', True)
    assert print_calls[1] == (' ' * 120, '\r', True)
    assert '更新完成' in messages


def test_runtime_launcher_first_clone_continues_on_runtime_incompatible(monkeypatch) -> None:
    warnings: list[str] = []
    exit_calls: list[int] = []

    class FakeGitService:
        def is_initial_checkout_pending(self) -> bool:
            return True

        def fetch_latest_code(self, progress_callback=None, initial_tag=None):
            return (
                git_service_module.GitSyncStatus.RUNTIME_INCOMPATIBLE,
                git_service_module.GitSyncStatus.RUNTIME_INCOMPATIBLE.value,
            )

    monkeypatch.setattr(
        env_context_module,
        'OneDragonEnvContext',
        lambda: SimpleNamespace(
            env_config=SimpleNamespace(auto_update_code=True),
            git_service=FakeGitService(),
        ),
    )
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', lambda message: None)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.warning', warnings.append)
    monkeypatch.setattr('one_dragon.launcher.runtime_launcher.sys.exit', exit_calls.append)

    RuntimeLauncher('test', '1.0.0')._sync_code()

    assert exit_calls == []
    assert warnings == ['新版本需要更新启动器才能使用，继续使用当前版本']


def test_runtime_launcher_retries_builtin_release_tag_until_first_checkout(monkeypatch) -> None:
    warnings: list[str] = []
    received_tags: list[str | None] = []

    class FakeGitService:
        def is_initial_checkout_pending(self) -> bool:
            return True

        def fetch_latest_code(self, progress_callback=None, initial_tag=None):
            received_tags.append(initial_tag)
            return (
                git_service_module.GitSyncStatus.BUILTIN_TAG_UNAVAILABLE,
                git_service_module.GitSyncStatus.BUILTIN_TAG_UNAVAILABLE.value,
            )

    monkeypatch.setattr(
        env_context_module,
        'OneDragonEnvContext',
        lambda: SimpleNamespace(
            env_config=SimpleNamespace(auto_update_code=True),
            git_service=FakeGitService(),
        ),
    )
    monkeypatch.setattr('one_dragon.version.__version__', 'v1.2.3')
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', lambda message: None)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.warning', warnings.append)

    launcher = RuntimeLauncher('test', '1.0.0')
    launcher._sync_code()
    launcher._sync_code()

    assert received_tags == ['v1.2.3', 'v1.2.3']
    assert warnings == [
        '暂时无法获取当前版本所需文件，继续使用内置版本',
        '暂时无法获取当前版本所需文件，继续使用内置版本',
    ]


def test_runtime_launcher_up_to_date_does_not_clear_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    info_messages: list[str] = []
    clear_calls: list[set[str]] = []

    class FakeGitService:
        def is_initial_checkout_pending(self) -> bool:
            return False

        def fetch_latest_code(self, progress_callback=None, initial_tag=None):
            return (
                git_service_module.GitSyncStatus.UP_TO_DATE,
                git_service_module.GitSyncStatus.UP_TO_DATE.value,
            )

    monkeypatch.setattr(
        env_context_module,
        'OneDragonEnvContext',
        lambda: SimpleNamespace(
            env_config=SimpleNamespace(auto_update_code=True),
            git_service=FakeGitService(),
        ),
    )
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', info_messages.append)
    monkeypatch.setattr(
        RuntimeLauncher,
        '_clear_src_modules',
        lambda self, modules: clear_calls.append(modules),
    )

    RuntimeLauncher('test', '1.0.0')._sync_code()

    assert '当前已是最新版本' in info_messages
    assert clear_calls == []


@pytest.mark.parametrize(
    ('status', 'expected_warning'),
    [
        (git_service_module.GitSyncStatus.REMOTE_UNAVAILABLE, '暂时无法获取更新，继续使用当前版本'),
        (
            git_service_module.GitSyncStatus.LOCAL_CHANGES,
            '检测到程序文件有改动，未自动更新，继续使用当前版本',
        ),
    ],
)
def test_runtime_launcher_continues_when_existing_code_is_safe(
    monkeypatch: pytest.MonkeyPatch,
    status: git_service_module.GitSyncStatus,
    expected_warning: str,
) -> None:
    warnings: list[str] = []
    exit_calls: list[int] = []

    class FakeGitService:
        def is_initial_checkout_pending(self) -> bool:
            return False

        def fetch_latest_code(self, progress_callback=None, initial_tag=None):
            return status, status.value

    monkeypatch.setattr(
        env_context_module,
        'OneDragonEnvContext',
        lambda: SimpleNamespace(
            env_config=SimpleNamespace(auto_update_code=True),
            git_service=FakeGitService(),
        ),
    )
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', lambda message: None)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.warning', warnings.append)
    monkeypatch.setattr('one_dragon.launcher.runtime_launcher.sys.exit', exit_calls.append)

    RuntimeLauncher('test', '1.0.0')._sync_code()

    assert warnings == [expected_warning]
    assert exit_calls == []


@pytest.mark.parametrize(
    ('status', 'expected_error'),
    [
        (
            git_service_module.GitSyncStatus.LOCAL_UPDATE_FAILED,
            '更新没有完成，请重新运行启动器；仍然失败时请重新安装',
        ),
        (git_service_module.GitSyncStatus.FAILED, '更新失败，请查看日志后重试'),
    ],
)
@pytest.mark.parametrize('first_run', [True, False])
def test_runtime_launcher_stops_when_local_code_may_be_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    status: git_service_module.GitSyncStatus,
    expected_error: str,
    first_run: bool,
) -> None:
    errors: list[str] = []
    exit_calls: list[int] = []

    class FakeGitService:
        def is_initial_checkout_pending(self) -> bool:
            return first_run

        def fetch_latest_code(self, progress_callback=None, initial_tag=None):
            return status, status.value

    monkeypatch.setattr(
        env_context_module,
        'OneDragonEnvContext',
        lambda: SimpleNamespace(
            env_config=SimpleNamespace(auto_update_code=True),
            git_service=FakeGitService(),
        ),
    )
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', lambda message: None)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.error', errors.append)
    monkeypatch.setattr('one_dragon.launcher.runtime_launcher.sys.exit', exit_calls.append)

    RuntimeLauncher('test', '1.0.0')._sync_code()

    assert errors == [expected_error]
    assert exit_calls == [1]


def test_runtime_launcher_stops_when_first_fetch_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    errors: list[str] = []
    exit_calls: list[int] = []

    class FakeGitService:
        def is_initial_checkout_pending(self) -> bool:
            return True

        def fetch_latest_code(self, progress_callback=None, initial_tag=None):
            return (
                git_service_module.GitSyncStatus.REMOTE_UNAVAILABLE,
                git_service_module.GitSyncStatus.REMOTE_UNAVAILABLE.value,
            )

    monkeypatch.setattr(
        env_context_module,
        'OneDragonEnvContext',
        lambda: SimpleNamespace(
            env_config=SimpleNamespace(auto_update_code=True),
            git_service=FakeGitService(),
        ),
    )
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', lambda message: None)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.error', errors.append)
    monkeypatch.setattr('one_dragon.launcher.runtime_launcher.sys.exit', exit_calls.append)

    RuntimeLauncher('test', '1.0.0')._sync_code()

    assert errors == ['暂时无法获取更新，请稍后重试或切换代码源']
    assert exit_calls == [1]
