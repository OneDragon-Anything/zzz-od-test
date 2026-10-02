"""界面测试共用离屏 Qt；配置和运行记录写入临时目录。"""
from __future__ import annotations

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication
from test.harness.bagel import isolated_work_dir as isolated_work_dir


@pytest.fixture(scope='session')
def qapp() -> QApplication:
    """复用离屏 Qt。"""
    return QApplication.instance() or QApplication([])
