from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.envs.update_service import UpdateService


def _create_service() -> UpdateService:
    project_config = SimpleNamespace(project_name='TestProject')
    env_config = SimpleNamespace(repo_config=SimpleNamespace())
    git_service = SimpleNamespace()
    return UpdateService(project_config, env_config, git_service)


def test_runtime_dir_rename_retries_after_releasing_handles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _create_service()
    source = tmp_path / '.runtime'
    target = tmp_path / '.runtime.bak'
    source.mkdir()
    calls = {'rename': 0, 'released': 0}
    original_rename = Path.rename

    def rename_once(path: Path, destination: Path) -> Path:
        if path == source:
            calls['rename'] += 1
            if calls['rename'] == 1:
                raise OSError('directory is locked')
        return original_rename(path, destination)

    def release_handles() -> None:
        calls['released'] += 1

    monkeypatch.setattr(Path, 'rename', rename_once)
    monkeypatch.setattr(service, '_release_runtime_dir_handles', release_handles)
    monkeypatch.setattr('one_dragon.envs.update_service.time.sleep', lambda _seconds: None)

    service._rename_runtime_dir(source, target)

    assert calls == {'rename': 2, 'released': 1}
    assert target.is_dir()
    assert not source.exists()
