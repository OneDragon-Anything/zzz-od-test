"""SuibianTempleAdventureDispatch 随便观-游历派遣 op 测试。

用实拍 fixture(``screens/随便观/``)+ 纯逻辑节点覆盖派遣流程:
- ``check_screen``(游历):命中随便观-游历 → success。
- ``choose_period``(游历-选时间弹窗):命中 duration「20小时」→ round_wait(chosen_duration=True);
  ``chosen_duration=True`` 后命中「确认」→ round_success('确认')。
- ``click_auto_choose``(游历-选邦布):点 按钮-自动选择邦布 area → success。
- ``click_dispatch``(游历-派遣面板):OCR 命中「派遣」→ success。
- ``already_dispatch`` / ``cant_dispatch`` / ``dispatch_success``:纯 success 终态(不读画面,不需 fixture)。
- ``choose_period`` '提前收获' 分支:`test_choose_period_already_dispatched` 已覆盖(全屏兜底 OCR 命中「提前收获」→ round_success('提前收获'))。

未覆盖(留标记):
- ``choose_period_confirm_dialog`` / ``click_dispatch_confirm_dialog``:确认弹窗 fixture 未实拍(游戏派遣 UI 绕,「派遣」实为进选邦布界面,派遣确认弹窗未触发到)。
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

    def test_already_dispatch(self, test_context: TestContext) -> None:
        """已派遣(上游 status=提前收获)→ already_dispatch → status=已派遣(纯 success,不需 mock)。

        终态节点:上游 ``choose_period`` status='提前收获' 进此 → ``round_success('已派遣')``。
        """
        op = SuibianTempleAdventureDispatch(
            test_context, SuibianTempleAdventureDispatchDuration.HOUR_20
        )
        result = op.already_dispatch()
        assert result.status == '已派遣'

    def test_cant_dispatch(self, test_context: TestContext) -> None:
        """无法派遣(邦布电量不足 / 派遣确认)→ cant_dispatch → status=无法完成派遣(纯 success)。

        终态节点:上游 ``click_dispatch`` status='邦布电量不足' 或 ``click_dispatch_confirm_dialog``
        status='确认' 进此 → ``round_success(STATUS_CANT_DISPATCH='无法完成派遣')``。
        """
        op = SuibianTempleAdventureDispatch(
            test_context, SuibianTempleAdventureDispatchDuration.HOUR_20
        )
        result = op.cant_dispatch()
        assert result.status == '无法完成派遣'

    def test_dispatch_success(self, test_context: TestContext) -> None:
        """派遣成功(点派遣后无确认弹窗)→ dispatch_success → status=派遣成功(纯 success)。

        终态节点:上游 ``click_dispatch_confirm_dialog`` ``success=False``(没出现对话框的确认)进此
        → ``round_success('派遣成功')``,是 ``AdventureSquad.choose_mission`` 后的正常出口。
        """
        op = SuibianTempleAdventureDispatch(
            test_context, SuibianTempleAdventureDispatchDuration.HOUR_20
        )
        result = op.dispatch_success()
        assert result.status == '派遣成功'

    def test_choose_period_confirm(self, test_context: TestContext) -> None:
        """选时间弹窗 + 已选 duration(chosen_duration=True)→ choose_period 命中「确认」→ round_success('确认')。

        ``choose_period`` 首次(chosen_duration=False)target 含 duration,先命中 duration;
        置 ``chosen_duration=True`` 后 target 仅「确认」→ 命中 → ``round_success('确认')``
        (进 ``choose_period_confirm_dialog``)。复用 游历-选时间弹窗 fixture。
        """
        test_context.mock_screen('随便观', '游历-选时间弹窗')
        op = SuibianTempleAdventureDispatch(
            test_context, SuibianTempleAdventureDispatchDuration.HOUR_20
        )
        op.chosen_duration = True  # 模拟已选 duration,本轮点确认
        op.screenshot()
        result = op.choose_period()
        assert result.is_success, 'chosen_duration 后应命中「确认」'
        assert result.status == '确认'

    def test_choose_period_already_dispatched(self, test_context: TestContext) -> None:
        """已派遣态(副本进行中,显示「提前收获」)→ choose_period → status=提前收获。

        副本已派遣时无选时间弹窗(duration / 确认 不在 ``弹窗-游历时间选择`` area),
        ``choose_period`` 走兜底 ``round_by_ocr('提前收获')`` 全屏命中 →
        ``round_success('提前收获')``(进 ``already_dispatch`` 终态)。
        """
        op = self._make_op(test_context, '游历-已派遣态')
        result = op.choose_period()
        assert result.is_success, '已派遣态应命中提前收获'
        assert result.status == '提前收获'
