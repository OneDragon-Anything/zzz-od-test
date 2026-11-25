from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from zzz_od.context.zzz_context import ZContext


@pytest.mark.parametrize('region', ['cn', 'cn_b', 'us', 'eu', 'asia', 'twhkmo'])
def test_default_titles_do_not_depend_on_region(region: str) -> None:
    ctx = SimpleNamespace(game_account_config=SimpleNamespace(
        game_region=region, use_custom_win_title=False,
    ))
    assert ZContext.get_window_titles(ctx) == ['绝区零', 'ZenlessZoneZero']


def test_custom_title_is_the_only_candidate() -> None:
    ctx = SimpleNamespace(game_account_config=SimpleNamespace(
        use_custom_win_title=True, custom_win_title='测试游戏',
    ))
    assert ZContext.get_window_titles(ctx) == ['测试游戏']


def test_init_controller_keeps_shared_window_object() -> None:
    from zzz_od.controller.zzz_pc_controller import ZPcController
    controller = Mock(spec=ZPcController)
    game_win = controller.game_win = Mock()
    controller.screenshot_method = 'old'
    controller.screenshot_controller = Mock()
    ctx = SimpleNamespace(
        game_account_config=SimpleNamespace(platform='PC'),
        controller=controller, game_config=Mock(),
        env_config=SimpleNamespace(screenshot_method='auto'),
        get_window_titles=lambda: ['绝区零', 'ZenlessZoneZero'],
    )
    with patch('zzz_od.controller.zzz_pc_controller.ZPcController', ZPcController):
        ZContext.init_controller(ctx)
    assert ctx.controller is controller
    assert ctx.controller.game_win is game_win
    controller.cleanup_after_app_shutdown.assert_not_called()
    controller.screenshot_controller.cleanup.assert_called_once()
    assert controller.screenshot_method == 'auto'
    controller.set_window_titles.assert_called_once_with(['绝区零', 'ZenlessZoneZero'])
    controller.screenshot_controller.cleanup.reset_mock()
    ZContext.init_controller(ctx)
    controller.screenshot_controller.cleanup.assert_not_called()
