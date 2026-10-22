from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEnum,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext


class StubRunContext:
    def __init__(self, current_app_id: str | None, registered: bool) -> None:
        self.current_app_id = current_app_id
        self.current_group_id = "group" if current_app_id is not None else None
        self.current_instance_idx = 0 if current_app_id is not None else None
        self.current_application = object() if current_app_id is not None else None
        self._run_state = ApplicationRunContextStateEnum.RUNNING
        self._registered = registered
        self.stop_calls = 0

    def is_app_registered(self, app_id: str) -> bool:
        return self._registered and app_id == self.current_app_id

    @property
    def is_context_stop(self) -> bool:
        return self._run_state == ApplicationRunContextStateEnum.STOP

    def stop_running(self) -> None:
        self.stop_calls += 1
        self._run_state = ApplicationRunContextStateEnum.STOP


class StubContext:
    _sync_current_application_after_refresh = (
        OneDragonContext._sync_current_application_after_refresh
    )

    def __init__(self, run_context: StubRunContext) -> None:
        self.run_context = run_context


def test_refresh_keeps_current_application_when_still_registered() -> None:
    run_context = StubRunContext("demo_app", registered=True)
    context = StubContext(run_context)

    context._sync_current_application_after_refresh()

    assert run_context.stop_calls == 0
    assert run_context.current_app_id == "demo_app"
    assert run_context.current_group_id == "group"
    assert run_context.current_application is not None


def test_refresh_stops_and_clears_removed_current_application() -> None:
    run_context = StubRunContext("removed_app", registered=False)
    context = StubContext(run_context)

    context._sync_current_application_after_refresh()

    assert run_context.stop_calls == 1
    assert run_context.current_app_id is None
    assert run_context.current_group_id is None
    assert run_context.current_instance_idx is None
    assert run_context.current_application is None
