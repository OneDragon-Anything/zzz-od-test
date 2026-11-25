import sys
from types import SimpleNamespace

import psutil
import pytest


def test_reads_only_bound_process(windows: SimpleNamespace) -> None:
    windows.add('ZenlessZoneZero', 1)
    windows.game.init_win()
    windows.add('绝区零', 2)
    windows.processes[1].exe.return_value = sys.executable
    assert windows.game.get_executable_path() == sys.executable
    windows.processes[2].exe.assert_not_called()
    windows.live[1].activate.assert_not_called()
    windows.live[1].restore.assert_not_called()


def test_missing_window(windows: SimpleNamespace) -> None:
    with pytest.raises(FileNotFoundError, match='未找到'):
        windows.game.get_executable_path()


@pytest.mark.parametrize('error', [psutil.AccessDenied(101), psutil.NoSuchProcess(101)])
def test_process_query_failure(windows: SimpleNamespace, error: psutil.Error) -> None:
    windows.add('绝区零', 1)
    windows.processes[1].exe.side_effect = error
    expected = psutil.AccessDenied if isinstance(error, psutil.AccessDenied) else FileNotFoundError
    with pytest.raises(expected):
        windows.game.get_executable_path()


def test_exit_during_read_does_not_read_another_process(windows: SimpleNamespace) -> None:
    windows.add('绝区零', 1)
    windows.add('ZenlessZoneZero', 2)
    process = windows.processes[1]

    def exit_while_reading() -> str:
        process.is_running.return_value = False
        return sys.executable

    process.exe.side_effect = exit_while_reading
    with pytest.raises(FileNotFoundError, match='退出'):
        windows.game.get_executable_path()
    windows.processes[2].exe.assert_not_called()
    assert windows.game._hWnd is None


@pytest.mark.parametrize('path', ['', 'C:/missing/game.exe', sys.prefix])
def test_invalid_path(windows: SimpleNamespace, path: str) -> None:
    windows.add('绝区零', 1)
    windows.processes[1].exe.return_value = path
    with pytest.raises(FileNotFoundError, match='无效'):
        windows.game.get_executable_path()
