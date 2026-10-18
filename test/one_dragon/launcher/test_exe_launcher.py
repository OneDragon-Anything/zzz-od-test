"""启动器版本输出的编码回归；仅在子进程中模拟各地区系统的本地编码。"""

import locale
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import one_dragon
from one_dragon.utils import app_utils

SRC_DIR = Path(one_dragon.__file__).resolve().parents[1]
DESCRIPTION = '绝区零 一条龙 启动器'
VERSION = 'v2.5.3'

# 子进程中运行真实的 show_version；pyuac 只在提权时使用，缺失时用空模块占位
SHOW_VERSION_SCRIPT = (
    'import sys, types\n'
    'try:\n'
    '    import pyuac\n'
    'except ImportError:\n'
    "    sys.modules['pyuac'] = types.ModuleType('pyuac')\n"
    'from one_dragon.launcher.exe_launcher import ExeLauncher\n'
    f'ExeLauncher({DESCRIPTION!r}, {VERSION!r}).show_version()\n'
)


def launcher_env(stdout_encoding: str) -> dict[str, str]:
    """模拟本地编码为 stdout_encoding 的系统：关闭 UTF-8 模式并指定管道编码。"""
    env = os.environ.copy()
    env.pop('PYTHONUTF8', None)
    env['PYTHONIOENCODING'] = stdout_encoding
    env['PYTHONPATH'] = str(SRC_DIR)
    return env


class TestShowVersionEncoding(unittest.TestCase):
    """启动器在任意本地编码下都能输出版本，且输出可被版本查询读取。"""

    ENCODINGS = ('cp936', 'cp1252', 'cp932', 'cp949')

    def run_show_version(self, stdout_encoding: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, '-X', 'utf8=0', '-B', '-c', SHOW_VERSION_SCRIPT],
            capture_output=True,
            env=launcher_env(stdout_encoding),
            timeout=60,
        )

    def test_output_is_utf8_under_any_locale(self) -> None:
        """本地编码无法表示中文描述时，也不能报错退出。"""
        for encoding in self.ENCODINGS:
            with self.subTest(encoding=encoding):
                result = self.run_show_version(encoding)
                self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
                self.assertEqual(
                    result.stdout.decode('utf-8').strip(),
                    f'{DESCRIPTION} {VERSION}',
                )

    @unittest.skipUnless(os.name == 'nt', '版本查询使用 Windows 启动标志')
    def test_version_query_reads_launcher_output(self) -> None:
        """版本查询在相同本地编码下读取真实的启动器输出。"""
        run = subprocess.run

        for encoding in self.ENCODINGS:
            thread_errors: list[threading.ExceptHookArgs] = []

            def run_launcher(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
                self.assertEqual(command, ['test-launcher.exe', '--version'])
                return run(
                    [sys.executable, '-X', 'utf8=0', '-B', '-c', SHOW_VERSION_SCRIPT],
                    **{**kwargs, 'env': launcher_env(encoding)},
                )

            with (
                self.subTest(encoding=encoding),
                patch.object(app_utils.subprocess, 'run', side_effect=run_launcher),
                patch.object(locale, 'getencoding', return_value=encoding),
                patch.object(threading, 'excepthook', side_effect=thread_errors.append),
            ):
                self.assertEqual(app_utils.get_exe_version('test-launcher.exe'), VERSION)
                self.assertEqual(thread_errors, [])


if __name__ == '__main__':
    unittest.main()
