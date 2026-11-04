"""OpenGame.wait_game 节点：窗口出现但激活不了时，不能当成成功继续走。"""

from types import SimpleNamespace

from zzz_od.operation.enter_game import open_game as open_game_module
from zzz_od.operation.enter_game.open_game import OpenGame


class _FakeController:

    def __init__(self, ready: bool, activated: bool):
        self.ready: bool = ready
        self.activated: bool = activated
        self.init_calls: int = 0
        self.active_calls: int = 0

    def init_game_win(self) -> None:
        self.init_calls += 1

    @property
    def is_game_window_ready(self) -> bool:
        return self.ready

    def active_window(self) -> bool:
        self.active_calls += 1
        return self.activated


def _make_op(controller: _FakeController) -> OpenGame:
    op = object.__new__(OpenGame)
    op.ctx = SimpleNamespace(controller=controller)
    op.activate_fail_times = 0
    op.round_success = lambda *args, **kwargs: ('success', kwargs)
    op.round_retry = lambda *args, **kwargs: ('retry', kwargs)
    op.round_fail = lambda *args, **kwargs: ('fail', args)
    return op


class TestOpenGameWaitGame:

    def test_window_not_ready_retries_without_activating(self):
        controller = _FakeController(ready=False, activated=False)

        result = OpenGame.wait_game(_make_op(controller))

        assert result[0] == 'retry'
        assert controller.active_calls == 0

    def test_activation_success_runs_hdr_and_succeeds(self, monkeypatch):
        executed: list[bool] = []
        monkeypatch.setattr(
            open_game_module, 'EnableAutoHDR',
            lambda ctx: SimpleNamespace(execute=lambda: executed.append(True)),
        )
        controller = _FakeController(ready=True, activated=True)

        result = OpenGame.wait_game(_make_op(controller))

        assert result[0] == 'success'
        assert executed == [True]

    def test_activation_failure_retries_then_fails(self):
        controller = _FakeController(ready=True, activated=False)
        op = _make_op(controller)

        results = [OpenGame.wait_game(op) for _ in range(OpenGame.ACTIVE_WINDOW_MAX_FAIL_TIMES)]

        assert [r[0] for r in results[:-1]] == ['retry'] * (OpenGame.ACTIVE_WINDOW_MAX_FAIL_TIMES - 1)
        assert results[-1][0] == 'fail'
        assert '激活失败' in results[-1][1][0]
        assert controller.active_calls == OpenGame.ACTIVE_WINDOW_MAX_FAIL_TIMES
