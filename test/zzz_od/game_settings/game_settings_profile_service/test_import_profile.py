import subprocess
from pathlib import Path

import pytest

from zzz_od.game_settings import game_settings_profile_service as service_module
from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileError,
    GameSettingsProfileService,
)


def test_import_profile_calls_reg_without_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "profile.reg"
    run_calls: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(service_module.shutil, "which", lambda executable: "reg.exe")

    def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
        run_calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(service_module.subprocess, "run", run)

    GameSettingsProfileService._import_profile(profile_path)

    assert run_calls[0][0] == ["reg.exe", "import", str(profile_path), "/reg:64"]
    assert "shell" not in run_calls[0][1]
    assert run_calls[0][1]["timeout"] == 30


def test_import_profile_reports_reg_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "profile.reg"
    monkeypatch.setattr(service_module.shutil, "which", lambda executable: "reg.exe")
    monkeypatch.setattr(
        service_module.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1),
    )

    with pytest.raises(GameSettingsProfileError, match="返回 1"):
        GameSettingsProfileService._import_profile(profile_path)
