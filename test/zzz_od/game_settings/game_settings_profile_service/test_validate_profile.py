from pathlib import Path
from types import SimpleNamespace

import pytest

from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileError,
    GameSettingsProfileService,
)


def _service() -> GameSettingsProfileService:
    ctx = SimpleNamespace(one_dragon_config=SimpleNamespace())
    return GameSettingsProfileService(ctx)


@pytest.mark.parametrize(
    ("registry_key", "encoding"),
    [
        (r"HKEY_CURRENT_USER\Software\miHoYo\绝区零", "utf-16"),
        (r"HKEY_CURRENT_USER\Software\miHoYo\ZenlessZoneZero", "utf-8-sig"),
    ],
)
def test_validate_profile_accepts_zzz_keys(
    tmp_path: Path,
    registry_key: str,
    encoding: str,
) -> None:
    profile_path = tmp_path / "profile.reg"
    profile_path.write_text(
        f'Windows Registry Editor Version 5.00\n\n[{registry_key}]\n"Quality"=dword:00000001\n',
        encoding=encoding,
    )

    assert _service().validate_profile(str(profile_path)) == profile_path.resolve()


@pytest.mark.parametrize(
    "body",
    [
        '[HKEY_CURRENT_USER\\Software\\OtherGame]\n"Quality"=dword:00000001\n',
        (
            '[HKEY_CURRENT_USER\\Software\\miHoYo\\绝区零]\n'
            '"Quality"=dword:00000001\n\n'
            '[HKEY_CURRENT_USER\\Software\\Microsoft]\n'
            '"Value"=dword:00000001\n'
        ),
        '[-HKEY_CURRENT_USER\\Software\\miHoYo\\绝区零]\n',
    ],
)
def test_validate_profile_rejects_keys_outside_zzz(tmp_path: Path, body: str) -> None:
    profile_path = tmp_path / "profile.reg"
    profile_path.write_text(
        f"Windows Registry Editor Version 5.00\n\n{body}",
        encoding="utf-8-sig",
    )

    with pytest.raises(GameSettingsProfileError, match="只允许"):
        _service().validate_profile(str(profile_path))


def test_validate_profile_rejects_non_reg_file(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.txt"
    profile_path.write_text("not a registry profile", encoding="utf-8")

    with pytest.raises(GameSettingsProfileError, match=".reg"):
        _service().validate_profile(str(profile_path))
