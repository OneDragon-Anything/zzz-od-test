from pathlib import Path
from unittest.mock import MagicMock

import pytest

from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


@pytest.mark.parametrize('pending', [False, True])
@pytest.mark.parametrize('limit,expected', [(1, True), (-1, False)])
def test_readiness_uses_current_config_and_preserves_old_record(
    config: BagelConfig, record: BagelRunRecord, legacy_collection: dict,
    pending: bool, limit: int, expected: bool,
) -> None:
    """不要求物资目标；旧局不拦截启动，也不能绕过当前配置校验。"""
    if not pending:
        legacy_collection['pending'] = None
        record.update('collection', legacy_collection)
    before = Path(record.file_path).read_bytes()
    config.data['max_success_rounds'] = limit
    ctx = MagicMock()
    result = BagelApp(ctx, config, record).check_ready()
    assert result.is_success is expected
    if not expected:
        assert result.is_fail
        assert '贝果配置无效' in result.status
    assert record.get('collection') == legacy_collection
    assert Path(record.file_path).read_bytes() == before
    assert not ctx.controller.mock_calls


def test_enter_refuses_settlement_with_safe_items(
    config: BagelConfig, record: BagelRunRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """结算仓库安全箱还有物资时，不触发下一局入场。"""
    screen = cv2_utils.read_image(str(
        Path(__file__).resolve().parents[5]
        / 'screens/贝果-仓库/满仓安全箱余一件-20260924.webp'
    ))
    ctx = MagicMock()
    ctx.controller.screenshot.return_value = (0.0, screen)
    app = BagelApp(ctx, config, record)
    monkeypatch.setattr(app, 'round_by_find_area', lambda *_args: MagicMock(is_success=True))
    result = app.enter()
    assert result.is_fail
    assert '安全箱仍有物资' in result.status
    ctx.controller.interact.assert_not_called()
    ctx.controller.click.assert_not_called()
