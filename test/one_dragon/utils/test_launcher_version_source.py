"""源码运行时不读取工作目录里别的启动器版本。"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import one_dragon.utils.app_utils as app_utils_module
from one_dragon.utils import app_utils


class TestGetLauncherVersion:

    def test_source_run_returns_empty(self, monkeypatch) -> None:
        """源码运行时进程不是启动器，工作目录的 exe 与本次运行无关。"""
        monkeypatch.setattr(app_utils_module, 'sys', SimpleNamespace(executable='python.exe'))
        query = MagicMock(return_value='9.9.9')
        monkeypatch.setattr(app_utils, 'get_exe_version', query)

        assert app_utils.get_launcher_version() == ''
        query.assert_not_called()

    def test_packaged_run_reads_current_exe(self, monkeypatch) -> None:
        """打包运行时读当前进程 exe 的版本。"""
        exe = 'C:/app/OneDragon-RuntimeLauncher.exe'
        monkeypatch.setattr(
            app_utils_module,
            'sys',
            SimpleNamespace(frozen=True, executable=exe),
        )
        query = MagicMock(return_value='1.2.3')
        monkeypatch.setattr(app_utils, 'get_exe_version', query)

        assert app_utils.get_launcher_version() == '1.2.3'
        query.assert_called_once_with(str(Path(exe)))
