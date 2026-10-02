from pathlib import Path
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel import bagel_const
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_factory import BagelFactory
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


def test_discover_and_create_daily_app() -> None:
    """按真实发现机制加载工厂，并使用指定分组配置。"""
    ctx = MagicMock()
    ctx.game_account_config.game_refresh_hour_offset = 4
    directory = Path(bagel_const.__file__).parent
    manager = ApplicationFactoryManager(ctx, [(directory, PluginSource.BUILTIN)])
    independent, daily = manager.discover_factories()
    assert independent == []
    assert [factory.app_id for factory in daily] == ['bagel']
    assert daily[0].priority == bagel_const.PRIORITY
    assert manager.scan_failures == []
    factory = daily[0]
    assert isinstance(factory, BagelFactory)
    app = factory.create_application(99, 'custom_group')
    assert app.config is factory.get_config(99, 'custom_group')
    assert Path(app.config.file_path).parent.name == 'custom_group'
    assert app.run_record.instance_idx == 99


def test_pending_round_reaches_entry_check(
    monkeypatch: pytest.MonkeyPatch, record: BagelRunRecord,
) -> None:
    """完整执行忽略旧局状态，进入入场核验并保留子操作的失败结果。"""
    ctx = MagicMock()
    ctx.game_account_config.game_refresh_hour_offset = 4
    ctx.run_context.is_context_stop = False
    ctx.run_context.is_context_pause = False
    ctx.run_context.is_app_need_notify.return_value = False
    ctx.is_game_window_ready = True
    factory = BagelFactory(ctx)
    app = factory.create_application(99, 'standalone')
    assert app.run_record.get('collection') == record.get('collection')
    monkeypatch.setattr(app, 'screenshot', lambda: None)
    monkeypatch.setattr(app, 'round_by_find_area', lambda *_: MagicMock(is_success=False))
    enter = MagicMock(return_value=OperationResult(False, '无法确认零携带'))
    monkeypatch.setattr(BagelEnter, 'execute', enter)
    result = app.execute()
    assert not result.success
    assert result.status == '无法确认零携带'
    enter.assert_called_once()
    assert app.run_record.get('collection') == record.get('collection')
