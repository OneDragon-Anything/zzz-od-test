from types import SimpleNamespace

import pytest

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.zzz_application import ZApplication


class FakeProfileService:

    def __init__(self) -> None:
        self.calls: list[str] = []

    def enter(self) -> bool:
        self.calls.append("enter")
        return True

    def exit(self) -> None:
        self.calls.append("exit")


def _application(service: FakeProfileService) -> ZApplication:
    app = object.__new__(ZApplication)
    app.ctx = SimpleNamespace(game_settings_profile_service=service)
    return app


def test_execute_wraps_application_with_profile_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeProfileService()
    result = OperationResult(success=True, status="完成")
    monkeypatch.setattr(Application, "execute", lambda self: result)

    assert ZApplication.execute(_application(service)) is result
    assert service.calls == ["enter", "exit"]


def test_execute_restores_profile_when_application_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeProfileService()

    def raise_error(self: Application) -> OperationResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(Application, "execute", raise_error)

    with pytest.raises(RuntimeError, match="boom"):
        ZApplication.execute(_application(service))

    assert service.calls == ["enter", "exit"]
