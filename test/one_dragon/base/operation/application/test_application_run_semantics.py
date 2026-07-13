from __future__ import annotations

from argparse import Namespace
from threading import Event

from one_dragon.base.config.one_dragon_config import AfterDoneOpEnum
from one_dragon.base.operation.application.application_finalizer import (
    AfterDoneRequest,
    execute_after_done,
    get_after_done_request_from_config,
    should_execute_after_done,
)
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
    ApplicationRunContextStateEventEnum,
    ApplicationRunResult,
    RunFinishReason,
)
from one_dragon.launcher.application_launcher import ApplicationLauncher


class DummyController:

    def __init__(self, init_success: bool = True):
        self.init_success: bool = init_success
        self.close_game_calls: int = 0

    def init_before_context_run(self) -> bool:
        return self.init_success

    def close_game(self) -> None:
        self.close_game_calls += 1


class DummyContext:

    def __init__(
        self,
        controller: DummyController | None = None,
        ready_for_application: bool = True,
    ):
        self.controller: DummyController | None = controller
        self.ready_for_application: bool = ready_for_application
        self.current_instance_idx: int = 1
        self.run_context: ApplicationRunContext = ApplicationRunContext(self)
        self.after_shutdown_calls: int = 0

    def after_app_shutdown(self) -> None:
        self.after_shutdown_calls += 1


class DummyFactory:

    def __init__(self, app_id: str, app):
        self.app_id: str = app_id
        self.app_name: str = app_id
        self.need_notify: bool = False
        self._app = app

    def create_application(self, instance_idx: int, group_id: str):
        return self._app

    def get_config(self, instance_idx: int, group_id: str):
        raise NotImplementedError

    def get_run_record(self, instance_idx: int):
        raise NotImplementedError


class CompletedApp:

    def execute(self) -> None:
        return None


class UserStoppedApp:

    def __init__(self, ctx: DummyContext):
        self.ctx: DummyContext = ctx

    def execute(self) -> None:
        self.ctx.run_context.stop_running(RunFinishReason.STOPPED_BY_USER)


class FlowStoppedApp:

    def __init__(self, ctx: DummyContext):
        self.ctx: DummyContext = ctx

    def execute(self) -> None:
        self.ctx.run_context.stop_running(RunFinishReason.STOPPED_BY_FLOW)


class FailedApp:

    def execute(self) -> None:
        raise RuntimeError("boom")


class AppShutdownApp:
    """模拟程序退出清理：运行中触发 after_app_shutdown。"""

    def __init__(self, ctx: DummyContext):
        self.ctx: DummyContext = ctx

    def execute(self) -> None:
        self.ctx.run_context.after_app_shutdown()


class TestApplicationRunContext:

    def test_run_application_completed(self) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", CompletedApp())
        )

        stop_payload: list[ApplicationRunResult] = []
        stop_event = Event()

        def on_stop(event) -> None:
            stop_payload.append(event.data)
            stop_event.set()

        ctx.run_context.event_bus.listen_event(
            ApplicationRunContextStateEventEnum.STOP, on_stop
        )

        result = ctx.run_context.run_application("dummy", 1, "group")

        assert result.finish_reason == RunFinishReason.COMPLETED
        assert ctx.run_context.last_run_result == result
        assert stop_event.wait(1)
        assert stop_payload[0].finish_reason == RunFinishReason.COMPLETED

    def test_run_application_completed_executes_after_done_request(
        self, monkeypatch
    ) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", CompletedApp())
        )
        action_order: list[tuple[str, int | None]] = []

        def fake_close_game() -> None:
            action_order.append(("close_game", None))

        def fake_shutdown(seconds: int) -> None:
            action_order.append(("shutdown", seconds))

        ctx.controller.close_game = fake_close_game
        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            fake_shutdown,
        )

        result = ctx.run_context.run_application(
            "dummy",
            1,
            "group",
            after_done_request=AfterDoneRequest(
                close_game=True,
                shutdown_seconds=120,
            ),
        )

        assert result.finish_reason == RunFinishReason.COMPLETED
        assert action_order == [("close_game", None), ("shutdown", 120)]

    def test_run_application_stopped_by_user(self) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", UserStoppedApp(ctx))
        )

        result = ctx.run_context.run_application("dummy", 1, "group")

        assert result.finish_reason == RunFinishReason.STOPPED_BY_USER

    def test_run_application_stopped_by_user_skips_after_done_request(
        self, monkeypatch
    ) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", UserStoppedApp(ctx))
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        result = ctx.run_context.run_application(
            "dummy",
            1,
            "group",
            after_done_request=AfterDoneRequest(
                close_game=True,
                shutdown_seconds=60,
            ),
        )

        assert result.finish_reason == RunFinishReason.STOPPED_BY_USER
        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_run_application_stopped_by_flow(self) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", FlowStoppedApp(ctx))
        )

        result = ctx.run_context.run_application("dummy", 1, "group")

        assert result.finish_reason == RunFinishReason.STOPPED_BY_FLOW

    def test_run_application_stopped_by_flow_skips_after_done_request(
        self, monkeypatch
    ) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", FlowStoppedApp(ctx))
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        result = ctx.run_context.run_application(
            "dummy",
            1,
            "group",
            after_done_request=AfterDoneRequest(
                close_game=True,
                shutdown_seconds=60,
            ),
        )

        assert result.finish_reason == RunFinishReason.STOPPED_BY_FLOW
        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_run_application_failed(self) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", FailedApp())
        )

        result = ctx.run_context.run_application("dummy", 1, "group")

        assert result.finish_reason == RunFinishReason.FAILED

    def test_run_application_failed_skips_after_done_request(
        self, monkeypatch
    ) -> None:
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", FailedApp())
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        result = ctx.run_context.run_application(
            "dummy",
            1,
            "group",
            after_done_request=AfterDoneRequest(
                close_game=True,
                shutdown_seconds=60,
            ),
        )

        assert result.finish_reason == RunFinishReason.FAILED
        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_run_application_completed_with_none_request_skips_actions(
        self, monkeypatch
    ) -> None:
        """结束后配置为 NONE（空 AfterDoneRequest）时，自然完成也不触发收尾。"""
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", CompletedApp())
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        result = ctx.run_context.run_application(
            "dummy",
            1,
            "group",
            after_done_request=AfterDoneRequest(),
        )

        assert result.finish_reason == RunFinishReason.COMPLETED
        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_run_application_init_timeout(self) -> None:
        ctx = DummyContext(
            controller=DummyController(),
            ready_for_application=False,
        )

        result = ctx.run_context.run_application("dummy", 1, "group", init_timeout=0)

        assert result.finish_reason == RunFinishReason.INIT_TIMEOUT

    def test_run_application_init_timeout_skips_after_done_request(
        self, monkeypatch
    ) -> None:
        ctx = DummyContext(
            controller=DummyController(),
            ready_for_application=False,
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        result = ctx.run_context.run_application(
            "dummy",
            1,
            "group",
            init_timeout=0,
            after_done_request=AfterDoneRequest(
                close_game=True,
                shutdown_seconds=60,
            ),
        )

        assert result.finish_reason == RunFinishReason.INIT_TIMEOUT
        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_run_application_init_failed(self) -> None:
        ctx = DummyContext(controller=None)
        ctx.run_context.registry_application(
            DummyFactory("dummy", CompletedApp())
        )

        result = ctx.run_context.run_application("dummy", 1, "group")

        assert result.finish_reason == RunFinishReason.INIT_FAILED

    def test_run_application_init_failed_skips_after_done_request(
        self, monkeypatch
    ) -> None:
        """未注册应用导致 INIT_FAILED 时，不执行关游戏/关机。"""
        ctx = DummyContext(controller=DummyController())
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        result = ctx.run_context.run_application(
            "unregistered",
            1,
            "group",
            after_done_request=AfterDoneRequest(
                close_game=True,
                shutdown_seconds=60,
            ),
        )

        assert result.finish_reason == RunFinishReason.INIT_FAILED
        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_after_app_shutdown_marks_app_shutdown(self) -> None:
        ctx = DummyContext(controller=DummyController())

        assert ctx.run_context.start_running() is True

        ctx.run_context.after_app_shutdown()

        assert ctx.run_context.last_run_result is not None
        assert (
            ctx.run_context.last_run_result.finish_reason
            == RunFinishReason.APP_SHUTDOWN
        )

    def test_run_application_app_shutdown_skips_after_done_request(
        self, monkeypatch
    ) -> None:
        """运行中触发 after_app_shutdown 时，不执行关游戏/关机。"""
        ctx = DummyContext(controller=DummyController())
        ctx.run_context.registry_application(
            DummyFactory("dummy", AppShutdownApp(ctx))
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        result = ctx.run_context.run_application(
            "dummy",
            1,
            "group",
            after_done_request=AfterDoneRequest(
                close_game=True,
                shutdown_seconds=60,
            ),
        )

        assert result.finish_reason == RunFinishReason.APP_SHUTDOWN
        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []


class TestApplicationFinalizer:

    def test_execute_after_done_completed_runs_actions(self, monkeypatch) -> None:
        ctx = DummyContext(controller=DummyController())
        result = ApplicationRunResult(
            finish_reason=RunFinishReason.COMPLETED,
            app_id="dummy",
            instance_idx=1,
            group_id="group",
        )
        action_order: list[tuple[str, int | None]] = []

        def fake_close_game() -> None:
            action_order.append(("close_game", None))

        def fake_shutdown(seconds: int) -> None:
            action_order.append(("shutdown", seconds))

        ctx.controller.close_game = fake_close_game
        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            fake_shutdown,
        )

        execute_after_done(
            ctx,
            result,
            AfterDoneRequest(close_game=True, shutdown_seconds=120),
        )

        assert action_order == [("close_game", None), ("shutdown", 120)]

    def test_execute_after_done_non_completed_noop(self, monkeypatch) -> None:
        ctx = DummyContext(controller=DummyController())
        result = ApplicationRunResult(
            finish_reason=RunFinishReason.FAILED,
            app_id="dummy",
            instance_idx=1,
            group_id="group",
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        execute_after_done(
            ctx,
            result,
            AfterDoneRequest(close_game=True, shutdown_seconds=60),
        )

        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_execute_after_done_stopped_by_user_noop(self, monkeypatch) -> None:
        ctx = DummyContext(controller=DummyController())
        result = ApplicationRunResult(
            finish_reason=RunFinishReason.STOPPED_BY_USER,
            app_id="dummy",
            instance_idx=1,
            group_id="group",
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        execute_after_done(
            ctx,
            result,
            AfterDoneRequest(close_game=True, shutdown_seconds=60),
        )

        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_execute_after_done_app_shutdown_noop(self, monkeypatch) -> None:
        ctx = DummyContext(controller=DummyController())
        result = ApplicationRunResult(
            finish_reason=RunFinishReason.APP_SHUTDOWN,
            app_id="dummy",
            instance_idx=1,
            group_id="group",
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        execute_after_done(
            ctx,
            result,
            AfterDoneRequest(close_game=True, shutdown_seconds=60),
        )

        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_should_execute_after_done_non_completed_reasons_return_false(self) -> None:
        non_completed_reasons = [
            RunFinishReason.STOPPED_BY_USER,
            RunFinishReason.STOPPED_BY_FLOW,
            RunFinishReason.FAILED,
            RunFinishReason.INIT_FAILED,
            RunFinishReason.INIT_TIMEOUT,
            RunFinishReason.APP_SHUTDOWN,
        ]

        for finish_reason in non_completed_reasons:
            result = ApplicationRunResult(
                finish_reason=finish_reason,
                app_id="dummy",
                instance_idx=1,
                group_id="group",
            )

            assert should_execute_after_done(
                result,
                AfterDoneRequest(close_game=True, shutdown_seconds=60),
            ) is False

    def test_execute_after_done_none_request_noop(self, monkeypatch) -> None:
        ctx = DummyContext(controller=DummyController())
        result = ApplicationRunResult(
            finish_reason=RunFinishReason.COMPLETED,
            app_id="dummy",
            instance_idx=1,
            group_id="group",
        )
        shutdown_calls: list[int] = []

        monkeypatch.setattr(
            "one_dragon.base.operation.application.application_finalizer.cmd_utils.shutdown_sys",
            lambda seconds: shutdown_calls.append(seconds),
        )

        execute_after_done(ctx, result, AfterDoneRequest())

        assert ctx.controller.close_game_calls == 0
        assert shutdown_calls == []

    def test_should_execute_after_done_completed_with_none_request_returns_false(self) -> None:
        result = ApplicationRunResult(
            finish_reason=RunFinishReason.COMPLETED,
            app_id="dummy",
            instance_idx=1,
            group_id="group",
        )

        assert should_execute_after_done(result, AfterDoneRequest()) is False

    def test_get_after_done_request_from_config_shutdown(self) -> None:
        request = get_after_done_request_from_config(
            AfterDoneOpEnum.SHUTDOWN.value.value
        )

        assert request.close_game is False
        assert request.shutdown_seconds == 60

    def test_get_after_done_request_from_config_none(self) -> None:
        request = get_after_done_request_from_config(
            AfterDoneOpEnum.NONE.value.value
        )

        assert request == AfterDoneRequest()


class DummyRunContextForLauncher:

    def __init__(self, result: ApplicationRunResult):
        self.result: ApplicationRunResult = result
        self.calls: list[tuple[str, int, str, AfterDoneRequest | None]] = []

    def run_application(
        self,
        app_id: str,
        instance_idx: int,
        group_id: str,
        after_done_request: AfterDoneRequest | None = None,
    ) -> ApplicationRunResult:
        self.calls.append((app_id, instance_idx, group_id, after_done_request))
        return self.result


class DummyLauncherContext:

    def __init__(self, result: ApplicationRunResult):
        self.current_instance_idx: int = 1
        self.run_context: DummyRunContextForLauncher = DummyRunContextForLauncher(result)
        self.after_shutdown_calls: int = 0

    def after_app_shutdown(self) -> None:
        self.after_shutdown_calls += 1


class DummyLauncher(ApplicationLauncher):

    def create_context(self):
        raise NotImplementedError


def test_application_launcher_passes_after_done_request_to_run_context() -> None:
    run_result = ApplicationRunResult(
        finish_reason=RunFinishReason.COMPLETED,
        app_id="one_dragon",
        instance_idx=1,
        group_id="one_dragon",
    )
    launcher = DummyLauncher()
    launcher.ctx = DummyLauncherContext(run_result)

    launcher.run_application(
        Namespace(close_game=True, shutdown=120)
    )

    assert launcher.ctx.run_context.calls == [
        ("one_dragon", 1, "one_dragon", AfterDoneRequest(True, 120))
    ]
    assert launcher.ctx.after_shutdown_calls == 1
