import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.config.game_account_config import GameRegionEnum
from zzz_od.game_settings import game_settings_profile_service as service_module
from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileError,
    GameSettingsProfileService,
)


def _write_profile(profile_path: Path, registry_key: str) -> None:
    profile_path.write_text(
        (
            'Windows Registry Editor Version 5.00\n\n'
            f'[{registry_key}]\n'
            '"Quality"=dword:00000001\n'
        ),
        encoding='utf-16',
    )


def _service(
    game_region: str,
    normal_profile_path: str = '',
) -> GameSettingsProfileService:
    config = SimpleNamespace(
        game_settings_profile_enabled=False,
        game_settings_profile_normal_path=normal_profile_path,
    )
    ctx = SimpleNamespace(
        controller=None,
        game_account_config=SimpleNamespace(game_region=game_region),
        one_dragon_config=config,
    )
    return GameSettingsProfileService(ctx)


@pytest.mark.parametrize(
    ('game_region', 'registry_key'),
    [
        (
            GameRegionEnum.CN.value.value,
            r'HKEY_CURRENT_USER\Software\miHoYo\绝区零',
        ),
        (
            GameRegionEnum.CNB.value.value,
            r'HKEY_CURRENT_USER\Software\miHoYo\绝区零',
        ),
        (
            GameRegionEnum.AMERICA.value.value,
            r'HKEY_CURRENT_USER\Software\miHoYo\ZenlessZoneZero',
        ),
    ],
)
def test_export_profile_closes_game_and_uses_current_region(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    game_region: str,
    registry_key: str,
) -> None:
    service = _service(game_region)
    calls: list[str] = []
    monkeypatch.setattr(service, '_close_game', lambda: calls.append('close'))

    def export_registry_key(key: str, profile_path: Path) -> None:
        calls.append(f'export:{key}:{profile_path.name}')
        _write_profile(profile_path, key)

    monkeypatch.setattr(service, '_export_registry_key', export_registry_key)

    result = service.export_profile(str(tmp_path / 'profile'))

    assert result == (tmp_path / 'profile.reg').resolve()
    assert calls == ['close', f'export:{registry_key}:profile.reg']


def test_export_profile_rejects_missing_parent_before_closing_game(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _service(GameRegionEnum.CN.value.value)
    calls: list[str] = []
    monkeypatch.setattr(service, '_close_game', lambda: calls.append('close'))

    with pytest.raises(GameSettingsProfileError, match='保存目录不存在'):
        service.export_profile(str(tmp_path / 'missing' / 'profile.reg'))

    assert calls == []


def test_export_profile_rejects_manual_action_during_automation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _service(GameRegionEnum.CN.value.value)
    service.enter()
    calls: list[str] = []
    monkeypatch.setattr(service, '_close_game', lambda: calls.append('close'))

    with pytest.raises(GameSettingsProfileError, match='运行中'):
        service.export_profile(str(tmp_path / 'profile.reg'))

    assert calls == []


def test_export_profile_rejects_action_while_profile_is_switching(
    tmp_path: Path,
) -> None:
    service = _service(GameRegionEnum.CN.value.value)
    service._action_lock.acquire()
    try:
        with pytest.raises(GameSettingsProfileError, match='正在切换'):
            service.export_profile(str(tmp_path / 'profile.reg'))
    finally:
        service._action_lock.release()


def test_export_registry_key_calls_reg_without_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / 'profile.reg'
    registry_key = r'HKEY_CURRENT_USER\Software\miHoYo\绝区零'
    run_calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(service_module.shutil, 'which', lambda executable: 'reg.exe')

    def run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        run_calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(service_module.subprocess, 'run', run)

    GameSettingsProfileService._export_registry_key(registry_key, profile_path)

    assert run_calls[0][0] == [
        'reg.exe',
        'export',
        registry_key,
        str(profile_path),
        '/y',
        '/reg:64',
    ]
    assert 'shell' not in run_calls[0][1]
    assert run_calls[0][1]['timeout'] == 30


def test_restore_normal_profile_closes_game_before_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    normal_profile_path = tmp_path / 'normal.reg'
    registry_key = r'HKEY_CURRENT_USER\Software\miHoYo\绝区零'
    _write_profile(normal_profile_path, registry_key)
    service = _service(
        GameRegionEnum.CN.value.value,
        normal_profile_path=str(normal_profile_path),
    )
    calls: list[str] = []
    monkeypatch.setattr(service, '_close_game', lambda: calls.append('close'))
    monkeypatch.setattr(
        service,
        '_import_profile',
        lambda path: calls.append(f'import:{path.name}'),
    )

    result = service.restore_normal_profile()

    assert result == normal_profile_path.resolve()
    assert calls == ['close', 'import:normal.reg']


def test_restore_normal_profile_rejects_manual_action_during_automation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    normal_profile_path = tmp_path / 'normal.reg'
    registry_key = r'HKEY_CURRENT_USER\Software\miHoYo\绝区零'
    _write_profile(normal_profile_path, registry_key)
    service = _service(
        GameRegionEnum.CN.value.value,
        normal_profile_path=str(normal_profile_path),
    )
    service.enter()
    calls: list[str] = []
    monkeypatch.setattr(service, '_close_game', lambda: calls.append('close'))

    with pytest.raises(GameSettingsProfileError, match='运行中'):
        service.restore_normal_profile()

    assert calls == []
