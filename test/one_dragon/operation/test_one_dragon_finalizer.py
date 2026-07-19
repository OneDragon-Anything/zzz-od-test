from unittest.mock import MagicMock, patch

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunResult,
    RunFinishReason,
)
from one_dragon.base.operation.one_dragon_finalizer import (
    AfterDoneRequest,
    execute_after_done,
)


def _run_result(finish_reason: RunFinishReason) -> ApplicationRunResult:
    return ApplicationRunResult(
        finish_reason=finish_reason,
        app_id='one_dragon',
        instance_idx=0,
        group_id='default',
    )


def test_execute_after_done_runs_both_requested_actions() -> None:
    ctx = MagicMock()
    request = AfterDoneRequest(close_game=True, shutdown_seconds=60)

    with patch('one_dragon.base.operation.one_dragon_finalizer.cmd_utils.shutdown_sys') as shutdown_sys:
        execute_after_done(ctx, _run_result(RunFinishReason.COMPLETED), request)

    ctx.controller.close_game.assert_called_once_with()
    shutdown_sys.assert_called_once_with(60)


def test_execute_after_done_skips_non_completed_run() -> None:
    ctx = MagicMock()
    request = AfterDoneRequest(close_game=True, shutdown_seconds=60)

    with patch('one_dragon.base.operation.one_dragon_finalizer.cmd_utils.shutdown_sys') as shutdown_sys:
        execute_after_done(ctx, _run_result(RunFinishReason.FAILED), request)

    ctx.controller.close_game.assert_not_called()
    shutdown_sys.assert_not_called()
