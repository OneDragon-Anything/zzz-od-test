"""``app_utils.get_exe_version`` 读取启动器版本号的单元测试。

重点:子进程输出按字节取回后自行解码。启动器 exe 由 PyInstaller 打包,在中文 Windows 上
输出 GBK 字节;若交给 ``subprocess`` 的 ``text=True`` 按本进程 locale 解码,则本进程处于
UTF-8 模式(如设置了 ``PYTHONUTF8=1``)时会抛 ``UnicodeDecodeError``、``stdout`` 变成
``None``,版本号被读成空字符串,界面就会一直误报"未安装"并反复提示更新。
"""

import subprocess
from collections.abc import Callable

import pytest

from one_dragon.utils import app_utils


def _fake_run(stdout: bytes) -> Callable[..., subprocess.CompletedProcess]:
    """构造一个假的 ``subprocess.run``,固定返回给定的原始输出字节。"""

    def _run(*args, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout)

    return _run


@pytest.mark.parametrize(
    ['raw', 'expected'],
    [
        # 中文 Windows 上启动器的实际输出是 GBK 字节
        ('绝区零 一条龙 启动器 v2.5.1\r\n'.encode('gbk'), 'v2.5.1'),
        ('绝区零 一条龙 启动器 v2.5.1\r\n'.encode(), 'v2.5.1'),
        (b'OneDragon Launcher v2.5.1\r\n', 'v2.5.1'),
    ],
    ids=['gbk', 'utf-8', 'ascii'],
)
def test_get_exe_version_decodes_output(
    monkeypatch: pytest.MonkeyPatch, raw: bytes, expected: str
) -> None:
    """不同编码的启动器输出都能读出末尾的版本号(回归 GBK 输出被按 UTF-8 解码失败)。"""
    monkeypatch.setattr(app_utils.subprocess, 'run', _fake_run(raw))
    assert app_utils.get_exe_version('OneDragon-Launcher.exe') == expected


def test_get_exe_version_strips_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    """输出带 ANSI 颜色转义(启动器用 colorama 上色)时先剥离,再取末尾版本号。"""
    raw = '\x1b[36m绝区零 一条龙 启动器 \x1b[0mv2.5.1\r\n'.encode('gbk')
    monkeypatch.setattr(app_utils.subprocess, 'run', _fake_run(raw))
    assert app_utils.get_exe_version('OneDragon-Launcher.exe') == 'v2.5.1'


def test_get_exe_version_empty_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """子进程没有输出时返回空字符串,不抛异常。"""
    monkeypatch.setattr(app_utils.subprocess, 'run', _fake_run(b''))
    assert app_utils.get_exe_version('OneDragon-Launcher.exe') == ''


def test_get_exe_version_returns_empty_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """子进程调用抛异常(如 exe 不存在)时返回空字符串。"""

    def _boom(*args, **kwargs) -> None:
        raise OSError('exe not found')

    monkeypatch.setattr(app_utils.subprocess, 'run', _boom)
    assert app_utils.get_exe_version('not-exist.exe') == ''


def test_decode_console_output_prefers_correct_encoding() -> None:
    """多编码回退能命中正确的那一种,不产生乱码。"""
    gbk_bytes = '绝区零 一条龙 启动器 v2.5.1'.encode('gbk')
    utf8_bytes = '绝区零 一条龙 启动器 v2.5.1'.encode()
    assert app_utils.decode_console_output(gbk_bytes).endswith('v2.5.1')
    assert app_utils.decode_console_output(utf8_bytes).endswith('v2.5.1')


def test_decode_console_output_fallback_does_not_raise() -> None:
    """既不是 UTF-8 也不是 GBK 的字节走宽松解码兜底,不抛异常。"""
    assert isinstance(app_utils.decode_console_output(b'\xff\xfe\xfa'), str)
