import time
from pathlib import Path

import pytest
import yaml
from test.harness.bagel import isolated_work_dir as isolated_work_dir

from one_dragon.base.operation.operation import Operation
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


@pytest.fixture(autouse=True)
def no_round_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """推进操作的等待时间，后台线程继续使用真实时钟。"""
    import sys

    from test.harness.bagel_clock import OperationClock

    clock = OperationClock()
    real_time = time
    for name, module in tuple(sys.modules.items()):
        if (
            name == 'one_dragon.base.operation.operation'
            or name == 'test.conftest'
            or name.startswith(
                (
                    'zzz_od.application.bagel.',
                    'test.harness.',
                    'test.zzz_od.application.bagel.',
                    'zzz-od-test.test.zzz_od.application.bagel.',
                )
            )
        ):
            if getattr(module, 'time', None) is real_time:
                monkeypatch.setattr(module, 'time', clock)

    def skip_wait(
        self: Operation, wait: float | None = None, wait_round_time: float | None = None
    ) -> None:
        clock.sleep(
            wait
            or max(0, (wait_round_time or 0) - (clock.time() - self.round_start_time))
        )

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
    path.write_text(
        yaml.safe_dump({'collection': legacy_collection}, allow_unicode=True),
        encoding='utf-8',
    )
    return BagelRunRecord(99)


FAST_GROUPS = {'bagel_config', 'bagel_flow', 'bagel_run_record'}

FAST_BEHAVIORS = {
    'test_all_exits_remove_run_listeners',
    'test_all_known_qualities_outrank_lower_qualities_and_unknown',
    'test_full_return_label',
    'test_non_contiguous_selection_skips_unchecked',
    'test_parse_capacity_pair',
    'test_parse_filter_count',
    'test_queued_callback_cannot_reach_finished_or_reused_operation',
    'test_release_timed_and_drag_inputs',
    'test_same_quality_uses_hardcoded_type_order',
    'test_sequence_stops_at_failed_step',
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """日常集显式维护，完整回归仍运行全部贝果场景。"""
    for item in items:
        if (
            'bagel' in item.path.parts
            and item.path.parent.name in FAST_GROUPS
            or item.originalname in FAST_BEHAVIORS
        ):
            item.add_marker(pytest.mark.bagel_fast)
