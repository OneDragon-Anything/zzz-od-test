"""画面识别线程：只遍历启动时的候选列表。"""

import numpy as np

from one_dragon_qt.view.devtools import devtools_screen_manage_interface as devtools


class _FakeScreenInfo:

    def __init__(self, screen_name: str) -> None:
        self.screen_name = screen_name


class _FakeLoader:

    def __init__(self, screens: list[_FakeScreenInfo]) -> None:
        self.screen_info_list = screens


class _FakeCtx:

    def __init__(self, screens: list[_FakeScreenInfo]) -> None:
        self.screen_loader = _FakeLoader(screens)


def test_worker_uses_snapshot_and_reports_checked_count(monkeypatch) -> None:
    screens = [_FakeScreenInfo('画面A'), _FakeScreenInfo('画面B')]
    ctx = _FakeCtx(screens)
    screen = np.zeros((4, 4, 3), dtype=np.uint8)
    seen: list[str] = []

    def fake_get_names(_ctx, _screen, screen_info_list=None, crop_first=True) -> list[str]:
        seen.extend(info.screen_name for info in screen_info_list)
        return ['画面A']

    monkeypatch.setattr(devtools.screen_utils, 'get_match_screen_names', fake_get_names)

    worker = devtools.ScreenMatchWorker(ctx, screen, list(screens))
    emitted: list[list[str]] = []
    worker.done.connect(emitted.append)
    worker.run()

    assert seen == ['画面A', '画面B']
    assert worker.checked_count == 2
    assert emitted == [['画面A']]
