"""贝果界面按被测方法组织的交互回归。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from one_dragon.envs.env_config import EnvConfig
from zzz_od.gui.view.bagel.bagel_route_editor import (
    BagelRouteEditor,
)


def test_stop_button_uses_main_program_key(
    editor: BagelRouteEditor,
) -> None:
    """独立启动读取主程序配置，复用上下文时显示其自定义按键。"""
    EnvConfig(MagicMock()).key_stop_running = 'f8'
    editor._refresh_stop_shortcut()
    assert editor.stop_button.text() == '停止 F8'
    editor.ctx = SimpleNamespace(key_stop_running='f7')
    editor._refresh_stop_shortcut()
    assert editor.stop_button.text() == '停止 F7'
    assert editor.stop_button.shortcut().isEmpty()
