"""每次启动重新统计连续失败。"""

from unittest.mock import MagicMock

from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


def test_handle_init_resets_defeat_streak(config: BagelConfig, record: BagelRunRecord) -> None:
    """上次达到停止上限不能影响用户再次启动。"""
    app = BagelApp(MagicMock(), config, record)
    app.defeat_rounds = 3
    app.handle_init()
    assert app.defeat_rounds == 0
