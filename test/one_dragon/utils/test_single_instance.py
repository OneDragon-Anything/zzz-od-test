"""单实例锁：同一目录不能同时开两个实例。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from one_dragon.utils.single_instance import (
    LOCK_FILE_NAME,
    SingleInstanceLock,
    acquire_instance_lock,
    release_instance_lock,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

_CHILD_SCRIPT = """
import sys
from pathlib import Path

from one_dragon.utils.single_instance import SingleInstanceLock

lock = SingleInstanceLock(Path(sys.argv[1]))
acquired = lock.acquire()
print('acquired' if acquired else 'blocked')
if acquired:
    lock.release()
"""


def _run_child(lock_path: Path) -> str:
    """在子进程里尝试获取同一把锁，返回 acquired / blocked。"""
    env = os.environ.copy()
    env['PYTHONPATH'] = str(REPO_ROOT / 'src')
    env['PYTHONIOENCODING'] = 'utf-8'
    result = subprocess.run(
        [sys.executable, '-c', _CHILD_SCRIPT, str(lock_path)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


class TestSingleInstanceLock:

    def test_acquire_writes_pid(self, tmp_path: Path) -> None:
        lock = SingleInstanceLock(tmp_path / 'a.lock')
        assert lock.acquire()
        try:
            assert lock.get_holder_pid() == str(os.getpid())
        finally:
            lock.release()

    def test_second_process_is_blocked(self, tmp_path: Path) -> None:
        lock = SingleInstanceLock(tmp_path / 'a.lock')
        assert lock.acquire()
        try:
            assert _run_child(tmp_path / 'a.lock') == 'blocked'
        finally:
            lock.release()

    def test_other_process_can_acquire_after_release(self, tmp_path: Path) -> None:
        lock = SingleInstanceLock(tmp_path / 'a.lock')
        assert lock.acquire()
        lock.release()

        assert _run_child(tmp_path / 'a.lock') == 'acquired'

    def test_lock_file_is_created_in_parent_dir(self, tmp_path: Path) -> None:
        lock = SingleInstanceLock(tmp_path / 'nested' / 'a.lock')
        assert lock.acquire()
        try:
            assert (tmp_path / 'nested' / 'a.lock').is_file()
        finally:
            lock.release()

    def test_release_is_idempotent(self, tmp_path: Path) -> None:
        lock = SingleInstanceLock(tmp_path / 'a.lock')
        assert lock.acquire()
        lock.release()
        lock.release()


class TestInstanceLockSingleton:

    def test_acquire_twice_in_same_process_is_allowed(self, tmp_path: Path) -> None:
        try:
            assert acquire_instance_lock(tmp_path)
            assert acquire_instance_lock(tmp_path)
        finally:
            release_instance_lock()

    def test_lock_file_name(self) -> None:
        assert LOCK_FILE_NAME == '.one_dragon.lock'

    def test_release_then_acquire_again(self, tmp_path: Path) -> None:
        assert acquire_instance_lock(tmp_path)
        release_instance_lock()

        assert acquire_instance_lock(tmp_path)
        release_instance_lock()