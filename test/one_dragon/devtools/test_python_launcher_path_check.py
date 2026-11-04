"""启动器工作目录检查的单元测试。

`verify_working_directory()` 以前遇到中文或空格路径直接 `sys.exit(1)`，
解压到中文目录的普通用户因此完全无法启动。现在改为只提示、继续启动，
这里验证提示内容、不再退出，以及工作目录确实切到了目标目录。
"""

import os
import sys
from pathlib import Path

import pytest

from one_dragon.devtools import python_launcher


@pytest.fixture
def restore_cwd():
    """`verify_working_directory()` 会 chdir，用例结束后切回原目录，避免污染其他用例。"""
    origin = os.getcwd()
    yield
    os.chdir(origin)


def test_ascii_path_has_no_problem() -> None:
    """纯英文无空格路径：没有任何提示。"""
    assert python_launcher.collect_path_problems(r'D:\OneDragon') == []


def test_chinese_path_reports_problem() -> None:
    """含中文：报非 ASCII 字符问题。"""
    problems = python_launcher.collect_path_problems(r'D:\绝区零\OneDragon')
    assert len(problems) == 1
    assert '非 ASCII' in problems[0]


def test_space_path_reports_problem() -> None:
    """含空格：报空格问题。"""
    problems = python_launcher.collect_path_problems(r'D:\My Tools\OneDragon')
    assert problems == ['路径中存在空格']


def test_bracket_path_reports_problem() -> None:
    """含方括号：报 PowerShell 通配符问题（#260 的已知失败）。"""
    problems = python_launcher.collect_path_problems(r'D:\[Game]\OneDragon')
    assert any('方括号' in problem for problem in problems)


def test_multiple_problems_all_reported() -> None:
    """中文 + 空格 + 方括号同时存在：三条都列出来，不只报第一条。"""
    problems = python_launcher.collect_path_problems(r'D:\[绝区零] 一条龙\OneDragon')
    assert len(problems) == 3


def test_verify_working_directory_continues_on_chinese_path(monkeypatch, tmp_path, capsys, restore_cwd) -> None:
    """中文 + 空格目录：照常返回工作目录并打印提示，不抛 SystemExit。"""
    target = tmp_path / '一条龙 测试'
    target.mkdir()
    monkeypatch.chdir(target)
    monkeypatch.setattr(sys, 'frozen', False, raising=False)

    cwd = python_launcher.verify_working_directory()

    assert Path(cwd) == target
    assert Path(os.getcwd()) == target
    out = capsys.readouterr().out
    assert '路径包含中文字符' in out
    assert '路径中存在空格' in out
    assert '继续启动' in out


def test_verify_working_directory_reports_pass_on_ascii_path(monkeypatch, tmp_path, capsys, restore_cwd) -> None:
    """纯 ASCII 目录：打印「目录核验通过」。

    临时目录本身可能落在含中文的用户目录下，这种环境直接跳过。
    """
    target = tmp_path / 'onedragon_ok'
    target.mkdir()
    if not str(target).isascii() or ' ' in str(target):
        pytest.skip('临时目录本身不是纯 ASCII 无空格路径')
    monkeypatch.chdir(target)
    monkeypatch.setattr(sys, 'frozen', False, raising=False)

    python_launcher.verify_working_directory()

    assert '目录核验通过' in capsys.readouterr().out


def test_frozen_launcher_uses_exe_directory(monkeypatch, tmp_path, capsys) -> None:
    """打包后的启动器（sys.frozen）：工作目录取 exe 所在目录，而不是当前目录。"""
    install_dir = tmp_path / '绝区零 一条龙'
    install_dir.mkdir()
    exe_path = install_dir / 'OneDragon-Launcher.exe'
    exe_path.write_bytes(b'')
    other_dir = tmp_path / 'elsewhere'
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(exe_path))

    cwd = python_launcher.verify_working_directory()

    assert Path(cwd) == install_dir
    assert Path(os.getcwd()) == install_dir
    assert '路径包含中文字符' in capsys.readouterr().out