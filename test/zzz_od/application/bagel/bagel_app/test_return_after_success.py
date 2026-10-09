"""完成提示使用真实返回结果，失败和无限次数不报正常完成。"""
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel import bagel_app
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


@pytest.mark.parametrize('status,success,limit', [('已返回贝果入口', True, 1), ('已返回大世界', True, 1), ('执行超时', False, 1), ('已返回贝果入口', True, 0)])
def test_return_after_success(config: BagelConfig, record: BagelRunRecord, monkeypatch: pytest.MonkeyPatch, status: str, success: bool, limit: int) -> None:
    """调用实际返回包装和完成判断，节点流转和计数保持原样。"""
    app = BagelApp(MagicMock(), config, record)
    app.success_rounds = 1
    config.max_success_rounds = limit
    logger = MagicMock()
    monkeypatch.setattr(bagel_app, 'log', logger)
    monkeypatch.setattr(bagel_app.BagelReturn, 'execute', lambda self: OperationResult(success, status))
    result = app.return_after_success()
    assert result.is_success == success
    if success:
        decision = app.decide_success_rounds()
        assert decision.status == ('已成功入仓 1 局' if limit else '继续入场')
    messages = [call.args[0] % call.args[1:] if len(call.args) > 1 else call.args[0] for call in logger.info.call_args_list]
    text = '\n'.join(messages)
    assert ('已达到成功次数上限' in text) == (success and limit > 0)
    if success and limit:
        assert ('并返回大世界' in text) == (status == '已返回大世界')
    assert app.success_rounds == 1 and app.failure_retries_used == 0
