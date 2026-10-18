"""版本查询的编码回归；仅启动输出固定字节的 Python 子进程。"""

import locale
import os
import subprocess
import sys
import threading
import unittest
from typing import Any
from unittest.mock import patch

from one_dragon.utils import app_utils


@unittest.skipUnless(os.name == 'nt', '版本查询使用 Windows 启动标志')
class TestExeVersionEncoding(unittest.TestCase):
    """通过真实管道验证编码边界，不启动游戏或启动器。"""

    def query_version(
        self,
        stdout: bytes,
        stderr: bytes = b'',
        local_encoding: str = 'cp936',
    ) -> str:
        """替换被查询程序，保留真实 subprocess 及其文本读取行为。"""
        run = subprocess.run
        thread_errors: list[threading.ExceptHookArgs] = []
        original_env = {
            key: os.environ.get(key)
            for key in ('PYTHONUTF8', 'PYTHONIOENCODING', '__COMPAT_LAYER', 'PYINSTALLER_RESET_ENVIRONMENT')
        }

        def run_fixture(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
            self.assertEqual(command, ['test-launcher.exe', '--version'])
            self.assertEqual(kwargs['env']['__COMPAT_LAYER'], 'RunAsInvoker')
            self.assertEqual(kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')
            self.assertEqual(kwargs['env'].get('PYTHONUTF8'), original_env['PYTHONUTF8'])
            script = (
                'import os; '
                f'os.write(1, bytes.fromhex({stdout.hex()!r})); '
                f'os.write(2, bytes.fromhex({stderr.hex()!r}))'
            )
            return run([sys.executable, '-B', '-c', script], **kwargs)

        with (
            patch.object(app_utils.subprocess, 'run', side_effect=run_fixture),
            patch.object(locale, 'getencoding', return_value=local_encoding),
            patch.object(threading, 'excepthook', side_effect=thread_errors.append),
        ):
            version = app_utils.get_exe_version('test-launcher.exe')
        self.assertEqual(thread_errors, [], '版本查询不应产生管道读取线程异常')
        self.assertEqual(
            {key: os.environ.get(key) for key in original_env}, original_env,
            '版本查询不能修改调用方环境',
        )
        return version

    def test_cp936_output_under_utf8_parent(self) -> None:
        """UTF-8 父进程读取中文本地编码输出时仍取得版本。"""
        self.assertEqual(
            self.query_version('绝区零 一条龙 启动器 v2.5.3\r\n'.encode('cp936')),
            'v2.5.3',
        )

    def test_utf8_output_with_non_utf8_locale(self) -> None:
        """不能为兼容本地编码而破坏 UTF-8 版本输出。"""
        self.assertEqual(
            self.query_version('启动器 v2.6.0\n'.encode('utf-8')),
            'v2.6.0',
        )

    def test_ascii_version(self) -> None:
        """保持纯 ASCII 版本号输出的行为。"""
        self.assertEqual(self.query_version(b'v2.7.1\r\n'), 'v2.7.1')

    def test_other_windows_locale(self) -> None:
        """不能把中文 Windows 编码硬编码给其他地区。"""
        self.assertEqual(
            self.query_version('Lanceur été v3.0.0\r\n'.encode('cp1252'), local_encoding='cp1252'),
            'v3.0.0',
        )

    def test_ansi_and_multiple_lines(self) -> None:
        """保持 ANSI 清理和取最后一个版本字段的现有行为。"""
        self.assertEqual(
            self.query_version('\x1b[32m提示\x1b[0m\r\n启动器 \x1b[36mv4.0.1\x1b[0m\r\n'.encode('cp936')),
            'v4.0.1',
        )

    def test_non_utf8_stderr_does_not_break_version(self) -> None:
        """版本 stdout 有效时，不应因无关 stderr 编码失败。"""
        self.assertEqual(
            self.query_version(b'Launcher v5.0.0\n', stderr='警告：仅供测试'.encode('cp936')),
            'v5.0.0',
        )

    def test_empty_output_returns_empty(self) -> None:
        """无输出继续按现有约定返回空串。"""
        self.assertEqual(self.query_version(b''), '')

    def test_invalid_output_returns_empty_without_thread_error(self) -> None:
        """两种编码均无效时安静失败，不吞字节后捏造版本。"""
        self.assertEqual(self.query_version(b'\x81'), '')

    def test_missing_executable_returns_empty(self) -> None:
        """保留不可执行程序的失败返回约定。"""
        with patch.object(app_utils.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(app_utils.get_exe_version('missing-launcher.exe'), '')


if __name__ == '__main__':
    unittest.main()
