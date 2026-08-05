from pathlib import Path
from types import SimpleNamespace

import pytest

from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileService,
)


def _write_profile(path: Path) -> None:
    path.write_text(
        (
            "Windows Registry Editor Version 5.00\n\n"
            "[HKEY_CURRENT_USER\\Software\\miHoYo\\绝区零]\n"
            '"Quality"=dword:00000001\n'
        ),
        encoding="utf-8-sig",
    )


def test_exit_restores_normal_profile_after_outer_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_path = tmp_path / "run.reg"
    normal_path = tmp_path / "normal.reg"
    _write_profile(run_path)
    _write_profile(normal_path)
    config = SimpleNamespace(
        game_settings_profile_enabled=True,
        game_settings_profile_run_path=str(run_path),
        game_settings_profile_normal_path=str(normal_path),
    )
    service = GameSettingsProfileService(
        SimpleNamespace(one_dragon_config=config, controller=None)
    )
    calls: list[str] = []
    monkeypatch.setattr(service, "_close_game", lambda: calls.append("close"))
    monkeypatch.setattr(
        service,
        "_import_profile",
        lambda path: calls.append(f"import:{path.name}"),
    )

    service.enter()
    service.enter()
    service.exit()
    assert calls == ["close", "import:run.reg"]

    service.exit()
    assert calls == [
        "close",
        "import:run.reg",
        "close",
        "import:normal.reg",
    ]
    assert service.session_depth == 0
