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


class TestApplyStagedRuntimeDir:

    def test_no_staged_dir_returns_false(self, tmp_path: Path) -> None:
        _make_dir(tmp_path / '.runtime', {'python.exe': b'old'})

        assert runtime_paths.apply_staged_runtime_dir(tmp_path) is False
        assert (tmp_path / '.runtime' / 'python.exe').read_bytes() == b'old'

    def test_swaps_staged_runtime_and_keeps_backup(self, tmp_path: Path) -> None:
        _make_dir(tmp_path / '.runtime', {'python.exe': b'old'})
        _make_dir(tmp_path / runtime_paths.RUNTIME_DIR_NEW, {'python.exe': b'new'})

        assert runtime_paths.apply_staged_runtime_dir(tmp_path) is True

        assert (tmp_path / '.runtime' / 'python.exe').read_bytes() == b'new'
        assert (tmp_path / '.runtime.bak' / 'python.exe').read_bytes() == b'old'
        assert not (tmp_path / runtime_paths.RUNTIME_DIR_NEW).exists()

    def test_first_install_without_old_runtime(self, tmp_path: Path) -> None:
        _make_dir(tmp_path / runtime_paths.RUNTIME_DIR_NEW, {'python.exe': b'new'})

        assert runtime_paths.apply_staged_runtime_dir(tmp_path) is True
        assert (tmp_path / '.runtime' / 'python.exe').read_bytes() == b'new'
        assert not (tmp_path / '.runtime.bak').exists()

    def test_replaces_existing_backup(self, tmp_path: Path) -> None:
        """上次留下的备份要被本次替换覆盖，不能挡住切换。"""
        _make_dir(tmp_path / '.runtime', {'python.exe': b'old'})
        _make_dir(tmp_path / '.runtime.bak', {'python.exe': b'older'})
        _make_dir(tmp_path / runtime_paths.RUNTIME_DIR_NEW, {'python.exe': b'new'})

        assert runtime_paths.apply_staged_runtime_dir(tmp_path) is True
        assert (tmp_path / '.runtime' / 'python.exe').read_bytes() == b'new'
        assert (tmp_path / '.runtime.bak' / 'python.exe').read_bytes() == b'old'

    def test_rename_failure_keeps_old_runtime(self, tmp_path: Path, monkeypatch) -> None:
        """旧目录改不了名时报错返回，不能把运行时弄丢。"""
        _make_dir(tmp_path / '.runtime', {'python.exe': b'old'})
        _make_dir(tmp_path / runtime_paths.RUNTIME_DIR_NEW, {'python.exe': b'new'})

        original_rename = Path.rename

        def fake_rename(self: Path, target: Path) -> Path:
            if self.name == '.runtime':
                raise OSError('WinError 5 拒绝访问')
            return original_rename(self, target)

        monkeypatch.setattr(Path, 'rename', fake_rename)

        assert runtime_paths.apply_staged_runtime_dir(tmp_path) is False
        assert (tmp_path / '.runtime' / 'python.exe').read_bytes() == b'old'
        assert (tmp_path / runtime_paths.RUNTIME_DIR_NEW / 'python.exe').exists()


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
