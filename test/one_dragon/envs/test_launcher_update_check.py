"""启动器版本检查只针对本次运行所用的启动器。"""

from types import SimpleNamespace

import one_dragon.envs.update_service as update_service_module
from one_dragon.envs.update_service import UpdateService


def _service() -> UpdateService:
    """构造不触网的服务实例，只测判断分支。"""
    return UpdateService.__new__(UpdateService)


class TestIsRunningPackagedLauncher:

    def test_source_run_is_not_packaged(self, monkeypatch) -> None:
        monkeypatch.setattr(update_service_module, 'sys', SimpleNamespace())

        assert UpdateService.is_running_packaged_launcher() is False

    def test_frozen_run_is_packaged(self, monkeypatch) -> None:
        monkeypatch.setattr(update_service_module, 'sys', SimpleNamespace(frozen=True))

        assert UpdateService.is_running_packaged_launcher() is True


class TestIsLauncherUpdateAvailable:

    def test_source_run_never_checks(self, monkeypatch) -> None:
        """源码运行不检查工作目录里启动器的版本。"""
        service = _service()
        monkeypatch.setattr(service, 'is_running_packaged_launcher', lambda: False)
        monkeypatch.setattr(
            service,
            'get_launcher_version_info',
            lambda *args, **kwargs: ('1.0.0', '2.0.0', ''),
        )

        assert service.is_launcher_update_available() is False

    def test_packaged_launcher_with_newer_version(self, monkeypatch) -> None:
        service = _service()
        monkeypatch.setattr(service, 'is_running_packaged_launcher', lambda: True)
        monkeypatch.setattr(service, 'detect_running_launcher_type', lambda: 'runtime')
        monkeypatch.setattr(
            service,
            'get_launcher_version_info',
            lambda *args, **kwargs: ('1.0.0', '1.0.1', '1.1.0-beta.1'),
        )

        assert service.is_launcher_update_available() is True

    def test_packaged_launcher_already_latest(self, monkeypatch) -> None:
        service = _service()
        monkeypatch.setattr(service, 'is_running_packaged_launcher', lambda: True)
        monkeypatch.setattr(service, 'detect_running_launcher_type', lambda: 'runtime')
        monkeypatch.setattr(
            service,
            'get_launcher_version_info',
            lambda *args, **kwargs: ('1.0.1', '1.0.1', '1.1.0-beta.1'),
        )

        assert service.is_launcher_update_available() is False

    def test_unknown_running_type_is_skipped(self, monkeypatch) -> None:
        service = _service()
        monkeypatch.setattr(service, 'is_running_packaged_launcher', lambda: True)
        monkeypatch.setattr(service, 'detect_running_launcher_type', lambda: None)
        monkeypatch.setattr(
            service,
            'get_launcher_version_info',
            lambda *args, **kwargs: ('1.0.0', '9.9.9', ''),
        )

        assert service.is_launcher_update_available() is False
