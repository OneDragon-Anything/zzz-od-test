"""OpenGame.wait_game 节点：窗口出现但激活不了时，不能当成成功继续走。"""

from types import SimpleNamespace

from one_dragon.base.operation.operation_base import OperationResult
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


def _patch_enable_hdr(monkeypatch, success: bool = True) -> list[bool]:
    """把 EnableAutoHDR 换成假实现，记录调用次数并返回指定结果。"""
    executed: list[bool] = []

    def fake_execute() -> OperationResult:
        executed.append(True)
        return OperationResult(success)

    monkeypatch.setattr(
        open_game_module, 'EnableAutoHDR',
        lambda ctx: SimpleNamespace(execute=fake_execute),
    )
    return executed


def _make_op(controller: _FakeController) -> OpenGame:
    op = object.__new__(OpenGame)
    op.ctx = SimpleNamespace(controller=controller)
    op.activate_fail_times = 0
    op.hdr_restored = False
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
        executed = _patch_enable_hdr(monkeypatch)
        controller = _FakeController(ready=True, activated=True)

        result = OpenGame.wait_game(_make_op(controller))

        assert result[0] == 'success'
        assert executed == [True]

    def test_activation_failure_retries_then_fails(self, monkeypatch):
        executed = _patch_enable_hdr(monkeypatch)
        controller = _FakeController(ready=True, activated=False)
        op = _make_op(controller)

        results = [OpenGame.wait_game(op) for _ in range(OpenGame.ACTIVE_WINDOW_MAX_FAIL_TIMES)]

        assert [r[0] for r in results[:-1]] == ['retry'] * (OpenGame.ACTIVE_WINDOW_MAX_FAIL_TIMES - 1)
        assert results[-1][0] == 'fail'
        assert '激活失败' in results[-1][1][0]
        assert controller.active_calls == OpenGame.ACTIVE_WINDOW_MAX_FAIL_TIMES
        assert executed == [True], '启动失败也要恢复 HDR，否则原始设置会被覆盖'
        assert op.hdr_restored is True, '已经恢复过就不要再兜底恢复一次'

    def test_window_not_ready_resets_activation_fail_count(self):
        controller = _FakeController(ready=False, activated=False)
        op = _make_op(controller)
        op.activate_fail_times = 3

        result = OpenGame.wait_game(op)

        assert result[0] == 'retry'
        assert op.activate_fail_times == 0, '窗口未就绪不算连续激活失败'

    def test_activation_failure_mentions_manual_hdr_when_restore_fails(self, monkeypatch):
        """HDR 恢复失败要在失败文案里给出恢复入口，不能静默丢掉原始设置。"""
        executed = _patch_enable_hdr(monkeypatch, success=False)
        controller = _FakeController(ready=True, activated=False)
        op = _make_op(controller)

        results = [OpenGame.wait_game(op) for _ in range(OpenGame.ACTIVE_WINDOW_MAX_FAIL_TIMES)]

        assert results[-1][0] == 'fail'
        assert '激活失败' in results[-1][1][0]
        # 恢复的是 HKCU\...\UserGpuPreferences 里按应用存的值，设置页的「切换 HDR 状态」写的也是它
        assert '切换 HDR 状态' in results[-1][1][0]
        assert executed == [True], 'HDR 恢复失败也只调用一次，不反复重试'

    def test_activation_success_ignores_hdr_restore_failure(self, monkeypatch):
        """窗口已经激活：HDR 恢复失败只记日志，不影响本次启动成功。"""
        _patch_enable_hdr(monkeypatch, success=False)
        controller = _FakeController(ready=True, activated=True)

        result = OpenGame.wait_game(_make_op(controller))

        assert result[0] == 'success'
        assert controller.active_calls == 1


class TestOpenGameRestoreHdrOnExit:
    """重试耗尽等失败退出路径也要恢复 HDR。"""

    def _patch_super(self, monkeypatch) -> None:
        monkeypatch.setattr(
            open_game_module.Operation, 'after_operation_done', lambda *args, **kwargs: None,
        )

    def test_failed_operation_restores_hdr(self, monkeypatch):
        executed = _patch_enable_hdr(monkeypatch)
        self._patch_super(monkeypatch)
        op = _make_op(_FakeController(ready=True, activated=False))

        OpenGame.after_operation_done(op, OperationResult(False, '超过最大重试次数'))

        assert executed == [True]
        assert op.hdr_restored is False, '恢复结果由 after_operation_done 自己判断，不改状态'

    def test_failed_operation_skips_hdr_when_already_restored(self, monkeypatch):
        executed = _patch_enable_hdr(monkeypatch)
        self._patch_super(monkeypatch)
        op = _make_op(_FakeController(ready=True, activated=False))
        op.hdr_restored = True

        OpenGame.after_operation_done(op, OperationResult(False, '连续激活失败'))

        assert executed == []

    def test_successful_operation_skips_hdr(self, monkeypatch):
        executed = _patch_enable_hdr(monkeypatch)
        self._patch_super(monkeypatch)
        op = _make_op(_FakeController(ready=True, activated=True))

        OpenGame.after_operation_done(op, OperationResult(True))

        assert executed == []
