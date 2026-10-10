"""流程编辑器窗口的创建与销毁。"""
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from zzz_od.gui.view.bagel.bagel_route_editor import BagelRouteEditor


@pytest.fixture(scope='function')
def editor(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[BagelRouteEditor]:
    """销毁前同步已保存标记，避免测试弹出模态确认。"""
    monkeypatch.setattr('zzz_od.gui.view.bagel.bagel_route_editor.RepoConfig', MagicMock())
    window = BagelRouteEditor(99)
    window.show()
    qapp.processEvents()
    yield window
    window.saved = dict(window.drafts)
    window.owns_context = False
    window.close()
    window.deleteLater()
    qapp.processEvents()
