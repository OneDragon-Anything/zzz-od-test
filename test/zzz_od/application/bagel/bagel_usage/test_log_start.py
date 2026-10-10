"""启动摘要必须来自当前配置，不能宣称关闭时仍会出售。"""
from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel import bagel_usage
from zzz_od.application.bagel.bagel_config import BagelConfig


@pytest.mark.parametrize('clean,custom,limit', [(False, True, 0), (True, False, 1), (True, True, 7)])
def test_log_start(config: BagelConfig, monkeypatch: pytest.MonkeyPatch, clean: bool, custom: bool, limit: int) -> None:
    """验证开关、筛选、无限次数和实际重试上限。"""
    config.auto_clean_warehouse = clean
    config.clean_mode = 'custom' if custom else 'default'
    config.clean_types = ['装备']
    config.clean_qualities = ['Z']
    config.max_success_rounds = limit
    config.max_failure_retries = 9
    logger = MagicMock()
    monkeypatch.setattr(bagel_usage, 'log', logger)
    bagel_usage.log_start(config)
    messages = [call.args[0] % call.args[1:] if len(call.args) > 1 else call.args[0] for call in logger.info.call_args_list]
    text = '\n'.join(messages)
    assert f'成功次数上限：{limit or "不限"}' in text
    assert '整体重试次数上限：9' in text
    assert '空箱结算跳过出售，仍核对安全箱和仓库容量；安全箱为空且容量可读时，满仓也可继续' in text
    assert '仍残留或满仓则停止' not in text
    assert ('出售范围：' in text) == clean
    if clean:
        assert ('装备、Z' in text) == custom
        assert '已有库存也会出售' in text
    else:
        assert '只入仓，不出售物品' in text
