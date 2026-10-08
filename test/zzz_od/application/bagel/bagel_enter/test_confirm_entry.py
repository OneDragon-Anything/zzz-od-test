from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_screen import read_area

if TYPE_CHECKING:
    from test.conftest import TestContext


def test_live_500k_frame_clicks_min_only(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
) -> None:
    """实际非零投资页必须识别单位及 MIN；仅模拟输入，不代表实机归零成功。"""
    test_context.mock_screen('贝果-入场确认', '高危投资500K-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.screenshot()
    assert read_area(test_context, op.last_screenshot, '贝果-入场确认', '投资金额') == '500K'
    assert op.round_by_find_area(op.last_screenshot, '贝果-入场确认', '投资标题').is_success
    assert op.round_by_find_area(op.last_screenshot, '贝果-入场确认', '投资最小值').is_success
    click = MagicMock(return_value=True)
    monkeypatch.setattr(test_context.controller, 'click', click)
    result = op.confirm_entry()
    assert result.result == OperationRoundResultEnum.WAIT
    assert result.status == '已点击 MIN，等待重新核对投资金额'
    click.assert_called_once()
    pos = click.call_args.args[0]
    assert 420 <= pos.x <= 550 and 775 <= pos.y <= 905
    assert not op.investment_confirmed


@pytest.mark.parametrize('amount', ['500000', '500K', '1M', '1.5M', '0.5M', '3M'])
def test_nonzero_investment_waits_for_new_zero_frame(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
    amount: str,
) -> None:
    """MIN 点击成功后仍未核验投资，下一帧明确为零才允许前往空洞。"""
    op = BagelEnter(test_context)
    op.zero_checked = True
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area == '投资标题' else op.round_retry()
    ))
    read = MagicMock(side_effect=[amount, '0'])
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.read_investment', read)
    click = MagicMock(return_value=op.round_success())
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)

    result = op.confirm_entry()
    assert result.result == OperationRoundResultEnum.WAIT
    assert click.call_args.args[2] == '投资最小值'
    assert not op.investment_confirmed
    assert read.call_count == 1

    result = op.confirm_entry()
    assert result.result == OperationRoundResultEnum.WAIT
    assert click.call_args.args[2] == '零投资前往空洞'
    assert op.investment_confirmed


@pytest.mark.parametrize('amount', ['', 'O', '00', '0.0', '0/500000', '?0', '500,000', '0K', '0M', '1.5', '5OOK', 'K'])
def test_unclear_investment_has_bounded_reads_without_clicks(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    no_round_wait: None, amount: str,
) -> None:
    """识别不明限次重读，不能把近似零当成零，也不能猜金额点击 MIN。"""
    op = BagelEnter(test_context)
    op.zero_checked = True
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area == '投资标题' else op.round_retry()
    ))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.read_investment', lambda *_: amount)
    click = MagicMock()
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)
    for _ in range(3):
        result = op.confirm_entry()
        assert result.result == OperationRoundResultEnum.RETRY
        assert result.status == '投资金额识别不明，重新核对'
    assert op.confirm_entry().is_fail
    assert not op.investment_confirmed
    click.assert_not_called()


@pytest.mark.parametrize('click_result', ['success', 'not_found', 'failed', 'unconfigured'])
def test_min_click_result_requires_recheck(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    no_round_wait: None, click_result: str,
) -> None:
    """点击、找不到按钮、输入失败和区域缺失都不能记为零投资已确认。"""
    op = BagelEnter(test_context)
    op.zero_checked = True
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area == '投资标题' else op.round_retry()
    ))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.read_investment', lambda *_: '1000000')
    results = {
        'success': op.round_success(),
        'not_found': op.round_retry('未找到 投资最小值'),
        'failed': op.round_retry('点击失败 投资最小值'),
        'unconfigured': op.round_fail('区域未配置 投资最小值'),
    }
    click = MagicMock(return_value=results[click_result])
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)
    result = op.confirm_entry()
    expected = OperationRoundResultEnum.WAIT if click_result == 'success' else results[click_result].result
    assert result.result == expected
    assert not op.investment_confirmed
    assert op.investment_retries == 1
    assert click.call_args.args[2] == '投资最小值'


def test_initial_zero_does_not_click_min(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
) -> None:
    """金额初始为零时直接确认入场，点击失败仍不能标记投资已确认。"""
    op = BagelEnter(test_context)
    op.zero_checked = True
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area == '投资标题' else op.round_retry()
    ))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.read_investment', lambda *_: '0')
    click = MagicMock(side_effect=[op.round_retry('点击失败'), op.round_success()])
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)
    assert op.confirm_entry().result == OperationRoundResultEnum.RETRY
    assert not op.investment_confirmed
    assert op.confirm_entry().result == OperationRoundResultEnum.WAIT
    assert op.investment_confirmed
    assert op.investment_retries == 0
    assert [call.args[2] for call in click.call_args_list] == ['零投资前往空洞'] * 2


def test_repeated_investment_does_not_change_amount(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
) -> None:
    """已经点击入场后不因金额闪动再次归零或确认。"""
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.investment_confirmed = True
    monkeypatch.setattr(op, 'round_by_find_area', lambda _screen, _name, area: (
        op.round_success() if area == '投资标题' else op.round_retry()
    ))
    monkeypatch.setattr('zzz_od.application.bagel.bagel_enter.read_investment', lambda *_: '500000')
    click = MagicMock()
    monkeypatch.setattr(op, 'round_by_find_and_click_area', click)
    assert op.confirm_entry().status == '零投资入场未生效'
    click.assert_not_called()


@pytest.mark.parametrize('investment_confirmed', [False, True])
def test_death_during_entry_is_forwarded_only_after_verified_investment(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
    investment_confirmed: bool,
) -> None:
    """零投资已确认的入场死亡交正式任务结算，不能绕过投资校验假称已入场。"""
    test_context.mock_screen('贝果-结算', '高危空局失败-原生1080')
    op = BagelEnter(test_context)
    op.zero_checked = True
    op.investment_confirmed = investment_confirmed
    op.screenshot()
    click = MagicMock()
    monkeypatch.setattr(test_context.controller, 'click', click)
    result = op.confirm_entry()
    assert result.is_success == investment_confirmed
    if investment_confirmed:
        assert result.status == '已进入雅努斯高危'
    click.assert_not_called()
