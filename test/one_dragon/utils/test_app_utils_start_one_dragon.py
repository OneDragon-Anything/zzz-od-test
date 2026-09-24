import os
import sys

import one_dragon.utils.app_utils as app_utils


def setup_popen_capture(monkeypatch) -> dict:
    """
    拦截 subprocess.Popen，捕获启动命令与环境变量
    """
    captured: dict = {}

    def fake_popen(cmd, shell=False, env=None):
        captured['cmd'] = cmd
        captured['env'] = env

    monkeypatch.setattr(app_utils.subprocess, 'Popen', fake_popen)
    return captured


def test_start_one_dragon_frozen_launches_launcher_next_to_exe(monkeypatch) -> None:
    """
    打包运行时（安装器 / 集成启动器）应启动当前 exe 同目录的 Launcher，
    而不是重新拉起自身
    """
    captured = setup_popen_capture(monkeypatch)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', r'D:\install\OneDragon-Installer.exe')

    app_utils.start_one_dragon(restart=False)

    assert r'D:\install\OneDragon-Launcher.exe' in captured['cmd']
    assert 'OneDragon-Installer.exe' not in captured['cmd']
    assert captured['env']['PYINSTALLER_RESET_ENVIRONMENT'] == '1'


def test_start_one_dragon_source_uses_work_dir(monkeypatch) -> None:
    """
    源码运行时从工作目录定位 Launcher，行为与打包前一致
    """
    captured = setup_popen_capture(monkeypatch)
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setattr(app_utils.os_utils, 'get_work_dir', lambda: r'D:\work')

    app_utils.start_one_dragon(restart=False)

    expected = os.path.join(r'D:\work', 'OneDragon-Launcher.exe')
    assert expected in captured['cmd']
    assert captured['env']['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
