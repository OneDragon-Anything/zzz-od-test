"""新任务重新统计成功、失败和额外入场次数。"""

from unittest.mock import MagicMock

from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


def test_handle_init_resets_failure_counts(config: BagelConfig, record: BagelRunRecord) -> None:
    """上次达到停止上限不能影响用户再次启动。"""
    app = BagelApp(MagicMock(), config, record)
    app.defeat_rounds = 3
    app.failure_retries_used = 2
    app.failure_retry_pending = True
    app.failure_reason = '上一任务失败'
    app.initial_clear_pending = False
    app.handle_init()
    assert app.defeat_rounds == 0
    assert app.failure_retries_used == 0
    assert not app.failure_retry_pending
    assert app.failure_reason is None
    assert app.initial_clear_pending
