from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from zzz_od.application.bagel.bagel_clean import FILTER_TICKS, BagelCleanWarehouse

if TYPE_CHECKING:
    from test.conftest import TestContext

    from one_dragon.base.operation.operation_round_result import OperationRoundResult

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.mark.parametrize(
    'initial',
    [
        set(FILTER_TICKS),
    ],
)
def test_filter_converges_from_existing_selection(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
    initial: set[str],
) -> None:
    """真实节点读取已有选择，点击会翻转；保护项必须清除，目标项不能反向取消。"""
    selected = initial.copy()
    op = BagelCleanWarehouse(test_context)
    monkeypatch.setattr(op, '_in_filter', lambda: True)
    names = (
        *FILTER_TICKS,
        '筛选-Z',
        '筛选-装备',
        '筛选-全部',
        '筛选-战术道具',
        '筛选-门禁卡',
    )
    monkeypatch.setattr(
        op,
        '_filter_states',
        lambda: {name: name in selected for name in names},
        raising=False,
    )

    def click(
        _screen: object, _page: str, name: str, **_kwargs: object
    ) -> OperationRoundResult:
        selected.symmetric_difference_update({name})
        return op.round_success(name)

    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)
    for _ in range(20):
        result = op.tick_filter()
        if result.status == '勾选完成':
            break
    assert result.status == '勾选完成'
    assert selected == set(FILTER_TICKS)


def test_ineffective_click_cannot_finish_filter(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """点击返回成功但画面不变时，不能继续读取件数和出售。"""
    op = BagelCleanWarehouse(test_context)
    monkeypatch.setattr(op, '_in_filter', lambda: True)
    monkeypatch.setattr(
        op, '_filter_states', lambda: dict.fromkeys(FILTER_TICKS, False)
    )
    monkeypatch.setattr(
        op, 'round_by_find_and_click_area', lambda *_args, **_kwargs: op.round_success()
    )
    for _ in range(3):
        assert not op.tick_filter().is_success


def test_filter_changed_before_count_stops(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """读数量前再次核对；多出的 Z 不能跟着目标项一起出售。"""
    op = BagelCleanWarehouse(test_context)
    monkeypatch.setattr(op, '_in_filter', lambda: True)
    monkeypatch.setattr(
        op,
        '_filter_states',
        lambda: {**dict.fromkeys(FILTER_TICKS, True), '筛选-Z': True},
    )
    assert op.read_count().is_fail
