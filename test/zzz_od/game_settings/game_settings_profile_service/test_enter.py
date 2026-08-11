from pathlib import Path
from types import SimpleNamespace

import pytest

from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileError,
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


def _service(tmp_path: Path) -> tuple[GameSettingsProfileService, Path, Path]:
    run_path = tmp_path / "run.reg"
    normal_path = tmp_path / "normal.reg"
    _write_profile(run_path)
    _write_profile(normal_path)
    config = SimpleNamespace(
        game_settings_profile_enabled=True,
        game_settings_profile_run_path=str(run_path),
        game_settings_profile_normal_path=str(normal_path),
    )
    ctx = SimpleNamespace(one_dragon_config=config, controller=None)
    return GameSettingsProfileService(ctx), run_path.resolve(), normal_path.resolve()


def test_enter_applies_run_profile_only_for_outer_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service, run_path, _ = _service(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(service, "_close_game", lambda: calls.append("close"))
    monkeypatch.setattr(
        service,
        "_import_profile",
        lambda path: calls.append(f"import:{path.name}"),
    )

    assert service.enter()
    assert service.enter()

    assert calls == ["close", f"import:{run_path.name}"]


def test_enter_restores_normal_profile_when_run_import_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service, run_path, normal_path = _service(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(service, "_close_game", lambda: calls.append("close"))

    def import_profile(path: Path) -> None:
        calls.append(f"import:{path.name}")
        if path == run_path:
            raise GameSettingsProfileError("导入失败")

    monkeypatch.setattr(service, "_import_profile", import_profile)

    with pytest.raises(GameSettingsProfileError, match="导入失败"):
        service.enter()

    assert calls == [
        "close",
        f"import:{run_path.name}",
        f"import:{normal_path.name}",
    ]
    assert service.session_depth == 0


def test_enter_keeps_disabled_outer_session_disabled_when_config_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(
        game_settings_profile_enabled=False,
        game_settings_profile_run_path="",
        game_settings_profile_normal_path="",
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

    assert service.enter()
    config.game_settings_profile_enabled = True
    assert service.enter()
    service.exit()
    service.exit()

    assert calls == []
    assert service.session_depth == 0
