from pathlib import Path

import pytest
import yaml
from test.harness.bagel import isolated_work_dir as isolated_work_dir

from one_dragon.base.operation.operation import Operation
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


@pytest.fixture
def no_round_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """仅跳过节点结果的等待；不替换线程、事件总线共用的 time.sleep。"""
    def skip_wait(
        self: Operation, wait: float | None = None, wait_round_time: float | None = None,
    ) -> None:
        """画面由测试剧本推进，节点无需等待真实时间。"""

    monkeypatch.setattr(Operation, '_after_round_wait', skip_wait)


@pytest.fixture
def config() -> BagelConfig:
    """返回当前应用组的默认配置。"""
    return BagelConfig(99, 'standalone')


@pytest.fixture
def legacy_collection() -> dict:
    """固定旧格式样本，不依赖已退役的记账接口制造历史文件。"""
    return {
        'version': 1,
        'targets': [{'name': '测试武备', 'variant': 'III', 'quantity': 2}],
        'deposited': [],
        'rounds': 1,
        'empty_rounds': 0,
        'failures': 0,
        'pending': {'id': 'legacy-round', 'phase': 'collecting', 'secured': []},
        'last_round': None,
    }


@pytest.fixture
def record(legacy_collection: dict) -> BagelRunRecord:
    """从旧 YAML 读取临时运行记录，验证当前应用保留旧数据。"""
    path = Path(BagelRunRecord(99).file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({'collection': legacy_collection}, allow_unicode=True), encoding='utf-8')
    return BagelRunRecord(99)
