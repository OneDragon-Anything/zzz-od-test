from types import SimpleNamespace

import pytest

from zzz_od.game_settings import game_settings_profile_service as service_module
from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileError,
    GameSettingsProfileService,
)


class FakeController:

    def __init__(self, closes_successfully: bool) -> None:
        self.is_game_window_ready: bool = True
        self.closes_successfully: bool = closes_successfully
        self.close_calls: int = 0

    def init_game_win(self) -> bool:
        return self.is_game_window_ready

    def close_game(self) -> None:
        self.close_calls += 1
        if self.closes_successfully:
            self.is_game_window_ready = False


def _service(controller: FakeController) -> GameSettingsProfileService:
    ctx = SimpleNamespace(controller=controller, one_dragon_config=SimpleNamespace())
    return GameSettingsProfileService(ctx)


def test_close_game_waits_until_window_disappears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = FakeController(closes_successfully=True)
    sleep_calls: list[float] = []
    monkeypatch.setattr(service_module.time, "sleep", sleep_calls.append)

    _service(controller)._close_game()

    assert controller.close_calls == 1
    assert sleep_calls == [0.5, 2]


def test_close_game_fails_when_window_stays_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = FakeController(closes_successfully=False)
    timestamps = iter([0.0, 31.0])
    monkeypatch.setattr(service_module.time, "monotonic", lambda: next(timestamps))
    monkeypatch.setattr(service_module.time, "sleep", lambda seconds: None)

    with pytest.raises(GameSettingsProfileError, match="关闭超时"):
        _service(controller)._close_game()

    assert controller.close_calls == 1
