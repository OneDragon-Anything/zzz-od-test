"""SuibianTempleAdventureDispatch 随便观-游历派遣 op 测试。

用实拍 fixture(``screens/随便观/``)覆盖派遣流程节点:
- ``check_screen``(游历):命中随便观-游历 → success。
- ``choose_period``(游历-选时间弹窗):命中 duration「20小时」→ round_wait(chosen_duration=True)。
- ``click_auto_choose``(游历-选邦布):点 按钮-自动选择邦布 area → success。
- ``click_dispatch``(游历-派遣面板):OCR 命中「派遣」→ success。

未覆盖(留标记):
- ``choose_period_confirm_dialog`` / ``click_dispatch_confirm_dialog``:确认弹窗 fixture 未实拍(游戏派遣 UI 绕,「派遣」实为进选邦布界面,派遣确认弹窗未触发到)。
- ``dispatch_success`` / ``cant_dispatch``:派遣成功/邦布电量不足分支,需真派遣或电量不足态。
"""
from test.conftest import TestContext

from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_dispatch import (
    SuibianTempleAdventureDispatch,
    SuibianTempleAdventureDispatchDuration,
)


class TestSuibianTempleAdventureDispatch:
    """随便观-游历派遣 op 测试。"""

    def _make_op(self, test_context: TestContext, state: str) -> SuibianTempleAdventureDispatch:
        test_context.mock_screen('随便观', state)
        op = SuibianTempleAdventureDispatch(
            test_context, SuibianTempleAdventureDispatchDuration.HOUR_20
        )
        op.screenshot()
        return op

    def test_check_screen_in_adventure(self, test_context: TestContext) -> None:
        """游历画面 → check_screen 命中随便观-游历 → success。"""
        op = self._make_op(test_context, '游历')
        result = op.check_screen()
        assert result.is_success, '游历画面应命中随便观-游历'

    def test_choose_period_select_duration(self, test_context: TestContext) -> None:
        """选时间弹窗(有「20小时」)→ choose_period 命中 duration → round_wait + chosen_duration=True。

        ``choose_period`` 命中 duration(非「确认」)时置 ``chosen_duration=True`` 并 ``round_wait``
        等下一轮点「确认」。故 ``is_success=False``、``status='20小时'``。
        """
        op = self._make_op(test_context, '游历-选时间弹窗')
        result = op.choose_period()
        assert result.status == '20小时', '应命中 duration 20小时'
        assert op.chosen_duration is True, '命中 duration 后应置 chosen_duration=True'

    def test_click_auto_choose(self, test_context: TestContext) -> None:
        """选邦布界面 → click_auto_choose 点 按钮-自动选择邦布 area → success。"""
        op = self._make_op(test_context, '游历-选邦布')
        result = op.click_auto_choose()
        assert result.is_success, '应命中 按钮-自动选择邦布 area'

    def test_click_dispatch(self, test_context: TestContext) -> None:
        """派遣面板(有「派遣」)→ click_dispatch OCR 命中「派遣」→ success。

        ``click_dispatch`` target=['邦布电量不足','派遣','可派遣小队'](ignore 可派遣小队);
        派遣面板有「派遣」→ 命中。
        """
        op = self._make_op(test_context, '游历-派遣面板')
        result = op.click_dispatch()
        assert result.is_success, '派遣面板应 OCR 命中「派遣」'
        assert result.status == '派遣'
