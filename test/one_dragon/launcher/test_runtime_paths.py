"""运行时目录的延后替换：新目录先落到 .runtime.new，下次启动才生效。"""

from pathlib import Path

from one_dragon.launcher import runtime_paths


def _make_dir(root: Path, files: dict[str, bytes]) -> Path:
    """按 {相对路径: 内容} 造目录。"""
    root.mkdir(parents=True, exist_ok=True)
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


class TestSwapScript:

    def test_script_waits_for_pid_then_swaps(self, tmp_path: Path) -> None:
        """脚本必须等进程退出，再换目录，避免进程占用时改名失败。"""
        script = runtime_paths.write_swap_script(tmp_path)

        text = script.read_text(encoding='utf-8')
        assert 'tasklist /FI "PID eq %TARGET_PID%"' in text
        assert text.index('%TARGET_PID%') < text.index('ren ".runtime" ".runtime.bak"')
        assert 'ren ".runtime.new" ".runtime"' in text
        assert 'ping -n 2 127.0.0.1' in text
        assert script.read_bytes().count(bytes([13, 10])) > 5

    def test_script_checks_new_runtime_before_moving_current(self, tmp_path: Path) -> None:
        """先确认 .runtime.new 在，再动当前 .runtime，否则会把运行时搬走又没东西补上。"""
        text = runtime_paths.write_swap_script(tmp_path).read_text(encoding='utf-8')
        assert text.index('if not exist ".runtime.new"') < text.index('ren ".runtime" ".runtime.bak"')

    def test_exe_copy_failure_keeps_new_file(self, tmp_path: Path) -> None:
        """.new exe 复制失败要保留并返回非零，下次启动还能重试。"""
        text = runtime_paths.write_swap_script(tmp_path).read_text(encoding='utf-8')
        copy_pos = text.index('copy /y "%EXE_NAME%.new"')
        assert text.index('if errorlevel 1', copy_pos) < text.index(
            'del "%EXE_NAME%.new"', copy_pos
        )

    def test_exe_copy_failure_rolls_back_swapped_runtime(self, tmp_path: Path) -> None:
        """运行时已经换好但 exe 复制失败时，要回滚运行时，别留下不匹配的组合。"""
        text = runtime_paths.write_swap_script(tmp_path).read_text(encoding='utf-8')
        assert 'set "RUNTIME_SWAPPED=1"' in text
        copy_pos = text.index('copy /y "%EXE_NAME%.new"')
        rollback_pos = text.index('ren ".runtime" ".runtime.new"', copy_pos)
        backup_pos = text.index('ren ".runtime.bak" ".runtime"', copy_pos)
        assert rollback_pos < backup_pos
        assert text.index('if "%RUNTIME_SWAPPED%"=="1"', copy_pos) < rollback_pos


class TestPendingSwap:

    def test_pending_new_exe_counts(self, tmp_path: Path) -> None:
        (tmp_path / 'OneDragon-RuntimeLauncher.exe.new').write_bytes(b'new')

        assert runtime_paths.has_pending_swap(tmp_path, 'OneDragon-RuntimeLauncher.exe') is True
        assert runtime_paths.has_pending_swap(tmp_path) is False


class TestScheduleRuntimeSwap:

    def test_no_staged_dir_does_not_start(self, tmp_path: Path, monkeypatch) -> None:
        _make_dir(tmp_path / '.runtime', {'python.exe': b'old'})
        started: list[object] = []

        def fake_popen(*args, **kwargs):
            started.append(args)

        monkeypatch.setattr(runtime_paths.subprocess, 'Popen', fake_popen)

        assert runtime_paths.schedule_runtime_swap(tmp_path, 1234) is False
        assert started == []

    def test_staged_dir_starts_script_with_pid(self, tmp_path: Path, monkeypatch) -> None:
        _make_dir(tmp_path / runtime_paths.RUNTIME_DIR_NEW, {'python.exe': b'new'})
        calls: list[list[str]] = []

        def fake_popen(args, **kwargs):
            calls.append(list(args))

        monkeypatch.setattr(runtime_paths.subprocess, 'Popen', fake_popen)

        assert runtime_paths.schedule_runtime_swap(tmp_path, 4321) is True

        assert len(calls) == 1
        assert calls[0][1] == '4321'
        assert calls[0][0].endswith('.bat')

    def test_popen_failure_returns_false(self, tmp_path: Path, monkeypatch) -> None:
        _make_dir(tmp_path / runtime_paths.RUNTIME_DIR_NEW, {'python.exe': b'new'})

        def fake_popen(*args, **kwargs):
            raise OSError('无法启动')

        monkeypatch.setattr(runtime_paths.subprocess, 'Popen', fake_popen)

        assert runtime_paths.schedule_runtime_swap(tmp_path, 1) is False


class TestStagedRuntimeDir:

    def test_stage_moves_dir(self, tmp_path: Path) -> None:
        staged = _make_dir(tmp_path / 'download' / '.runtime', {'python.exe': b'new'})
        work_dir = tmp_path / 'work'
        work_dir.mkdir()

        runtime_paths.stage_runtime_dir(staged, work_dir)

        assert (work_dir / '.runtime.new' / 'python.exe').read_bytes() == b'new'
        assert not staged.exists()

    def test_stage_replaces_previous_leftover(self, tmp_path: Path) -> None:
        _make_dir(tmp_path / 'work' / '.runtime.new', {'python.exe': b'older'})
        staged = _make_dir(tmp_path / 'download' / '.runtime', {'python.exe': b'new'})

        runtime_paths.stage_runtime_dir(staged, tmp_path / 'work')

        assert (tmp_path / 'work' / '.runtime.new' / 'python.exe').read_bytes() == b'new'

    def test_clear_removes_staged(self, tmp_path: Path) -> None:
        _make_dir(tmp_path / '.runtime.new', {'python.exe': b'new'})

        runtime_paths.clear_staged_runtime_dir(tmp_path)

        assert not (tmp_path / '.runtime.new').exists()

    def test_has_staged(self, tmp_path: Path) -> None:
        assert runtime_paths.has_staged_runtime(tmp_path) is False
        _make_dir(tmp_path / '.runtime.new', {'python.exe': b'new'})
        assert runtime_paths.has_staged_runtime(tmp_path) is True


class TestRuntimeDirsEqual:

    def test_same_content_different_timestamp(self, tmp_path: Path) -> None:
        left = _make_dir(tmp_path / 'left', {'a/base_library.zip': b'x'})
        right = _make_dir(tmp_path / 'right', {'a/base_library.zip': b'x'})

        assert runtime_paths.runtime_dirs_equal(left, right) is True

    def test_same_size_different_content(self, tmp_path: Path) -> None:
        left = _make_dir(tmp_path / 'left', {'python.exe': b'aaa'})
        right = _make_dir(tmp_path / 'right', {'python.exe': b'bbb'})

        assert runtime_paths.runtime_dirs_equal(left, right) is False

    def test_different_file_set(self, tmp_path: Path) -> None:
        left = _make_dir(tmp_path / 'left', {'python.exe': b'a'})
        right = _make_dir(tmp_path / 'right', {'python.exe': b'a', 'extra.dll': b'b'})

        assert runtime_paths.runtime_dirs_equal(left, right) is False

    def test_missing_dir(self, tmp_path: Path) -> None:
        left = _make_dir(tmp_path / 'left', {'python.exe': b'a'})

        assert runtime_paths.runtime_dirs_equal(left, tmp_path / 'missing') is False
