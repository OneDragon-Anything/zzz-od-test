"""把截图和所有画面逐个比对。"""

import numpy as np

from one_dragon.base.screen import screen_utils


class _FakeScreenInfo:
    """只带画面名的假 ScreenInfo。"""

    def __init__(self, screen_name: str) -> None:
        self.screen_name = screen_name


class _FakeScreenLoader:
    def __init__(self, screens: list[_FakeScreenInfo]) -> None:
        self.screen_info_list = screens


class _FakeCtx:
    def __init__(self, screens: list[_FakeScreenInfo]) -> None:
        self.screen_loader = _FakeScreenLoader(screens)


SCREEN = np.zeros((10, 10, 3), dtype=np.uint8)


class TestGetMatchScreenNames:

    def test_returns_matched_names_in_order(self, monkeypatch) -> None:
        screens = [_FakeScreenInfo('画面A'), _FakeScreenInfo('画面B'), _FakeScreenInfo('画面C')]
        ctx = _FakeCtx(screens)

        def fake_is_target(_ctx, _screen, screen_info=None, crop_first=True) -> bool:
            return screen_info.screen_name in ('画面A', '画面C')

        monkeypatch.setattr(screen_utils, 'is_target_screen', fake_is_target)

        assert screen_utils.get_match_screen_names(ctx, SCREEN) == ['画面A', '画面C']

    def test_returns_empty_when_nothing_matches(self, monkeypatch) -> None:
        ctx = _FakeCtx([_FakeScreenInfo('画面A')])
        monkeypatch.setattr(screen_utils, 'is_target_screen', lambda *args, **kwargs: False)

        assert screen_utils.get_match_screen_names(ctx, SCREEN) == []

    def test_uses_given_screen_list(self, monkeypatch) -> None:
        ctx = _FakeCtx([_FakeScreenInfo('画面A')])
        monkeypatch.setattr(screen_utils, 'is_target_screen', lambda *args, **kwargs: True)

        names = screen_utils.get_match_screen_names(
            ctx, SCREEN, screen_info_list=[_FakeScreenInfo('画面X')]
        )

        assert names == ['画面X']

    def test_single_screen_error_is_skipped(self, monkeypatch) -> None:
        screens = [_FakeScreenInfo('坏画面'), _FakeScreenInfo('好画面')]
        ctx = _FakeCtx(screens)

        def fake_is_target(_ctx, _screen, screen_info=None, crop_first=True) -> bool:
            if screen_info.screen_name == '坏画面':
                raise RuntimeError('识别崩了')
            return True

        monkeypatch.setattr(screen_utils, 'is_target_screen', fake_is_target)

        assert screen_utils.get_match_screen_names(ctx, SCREEN) == ['好画面']

    def test_does_not_modify_candidates(self, monkeypatch) -> None:
        screens = [_FakeScreenInfo('画面A')]
        ctx = _FakeCtx(screens)
        monkeypatch.setattr(screen_utils, 'is_target_screen', lambda *args, **kwargs: True)

        screen_utils.get_match_screen_names(ctx, SCREEN)

        assert ctx.screen_loader.screen_info_list == screens


class TestCandidateSnapshot:

    def test_reload_during_match_does_not_change_candidates(self, monkeypatch) -> None:
        """比对比对期间列表被 reload 清空时，本次比对仍按原候选列表走完。"""
        screens = [_FakeScreenInfo('画面A'), _FakeScreenInfo('画面B')]
        ctx = _FakeCtx(screens)
        seen: list[str] = []

        def fake_is_target(_ctx, _screen, screen_info=None, crop_first=True) -> bool:
            seen.append(screen_info.screen_name)
            if len(seen) == 1:
                # 模拟保存画面触发 reload：原地清空并重新填充
                ctx.screen_loader.screen_info_list.clear()
                ctx.screen_loader.screen_info_list.append(_FakeScreenInfo('画面C'))
            return True

        monkeypatch.setattr(screen_utils, 'is_target_screen', fake_is_target)

        names = screen_utils.get_match_screen_names(ctx, SCREEN)

        assert names == ['画面A', '画面B']
        assert seen == ['画面A', '画面B']
