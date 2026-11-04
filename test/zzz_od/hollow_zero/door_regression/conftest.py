from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from one_dragon.base.screen.screen_loader import ScreenContext
from zzz_od.application.hollow_zero.withered_domain.withered_domain_context import (
    WitheredDomainContext,
)
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig


@pytest.fixture
def door_context(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """只加载地图数据和画面配置，不启动游戏或读取用户配置。"""
    monkeypatch.setattr('time.sleep', lambda _: None)
    loader = ScreenContext()
    loader.reload()
    ctx = SimpleNamespace(
        screen_loader=loader,
        controller=Mock(),
        env_config=SimpleNamespace(is_debug=True),
        run_context=Mock(),
        current_instance_idx=99,
        debug_trace_bus=None,
    )
    ctx.withered_domain = WitheredDomainContext(ctx)
    ctx.withered_domain.data_service.reload()
    ctx.withered_domain.challenge_config = HollowZeroChallengeConfig('', is_mock=True)
    ctx.withered_domain.check_info_before_move = Mock()
    return ctx


@pytest.fixture(scope='session')
def door_image() -> Path:
    """真实截图归档位置。"""
    return Path(__file__).resolve().parents[4] / 'screens/零号空洞-事件/door_battle.webp'
