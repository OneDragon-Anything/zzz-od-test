"""SuibianTempleAdventureSquad 随便观-游历 op 测试(离线可测节点)。

覆盖不需实拍 fixture 的节点(纯逻辑 / 守卫 / 复用现有 fixture):
- ``execute_dispatch_1`` 守卫:dispatch=False → status=跳过派遣(不委托 AdventureDispatch)。
- ``prepare_to_choose_mission`` 3 分支(纯 idx 逻辑,不读画面):
  - dispatch=False → 跳过派遣;
  - dispatch=True + idx 走完 → 已完成所有副本选择;
  - dispatch=True + idx 未走完 → round_success(无 status,idx 自增进选副本)。
- ``back_to_entry`` success:已在随便观-入口 → round_success(复用 入口-手动态 fixture)。

未覆盖(需实拍 / 流程测试,见 ``随便观.md`` 备注):
- ``click_claim`` / ``click_confirm``:收获确认链,需「可收获 / 确认」中间态 fixture(待实拍)。
- ``choose_mission`` / ``choose_sub_mission``:派遣选副本,需副本列表 fixture(待实拍)。
- ``execute_dispatch_1`` / ``execute_dispatch_2`` 委托分支:跑 ``AdventureDispatch`` 完整流程,需 FixtureController 流程测试。
- ``click_squad_team`` / ``click_finish`` / ``goto_adventure``:见 ``test_suibian_temple_app.py``。
"""
from test.conftest import TestContext

from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_squad import (
    SuibianTempleAdventureSquad,
)


class TestSuibianTempleAdventureSquad:
    """随便观-游历 op 测试(离线可测节点)。"""

    def test_execute_dispatch_1_skip_dispatch(self, test_context: TestContext) -> None:
        """dispatch=False → execute_dispatch_1 守卫 → status=跳过派遣(不委托 AdventureDispatch)。

        ``execute_dispatch_1`` 首行 ``if not self.dispatch: return round_success('跳过派遣')``
        是显式守卫(动作一「混合」类:先守卫,过守卫才委托子 op)。不读画面,不需 mock。
        """
        op = SuibianTempleAdventureSquad(test_context, claim=True, dispatch=False)
        result = op.execute_dispatch_1()
        assert result.is_success, '守卫分支应 round_success'
        assert result.status == '跳过派遣', 'dispatch=False 应跳过派遣'

    def test_prepare_to_choose_mission_skip_dispatch(self, test_context: TestContext) -> None:
        """dispatch=False → prepare_to_choose_mission 守卫 → status=跳过派遣。"""
        op = SuibianTempleAdventureSquad(test_context, dispatch=False)
        result = op.prepare_to_choose_mission()
        assert result.status == '跳过派遣', 'dispatch=False 应跳过派遣'

    def test_prepare_to_choose_mission_all_done(self, test_context: TestContext) -> None:
        """dispatch=True + idx 已到 mission_list 末尾 → status=已完成所有副本选择。

        ``mission_list = ['fake', m1, m2, m3, m4]``(len=5)。设 ``current_mission_idx=4``(末尾),
        调 ``prepare`` → ``+1=5 >= 5`` → ``已完成所有副本选择``(下游 ``back_to_entry`` 的
        ``@node_from`` 匹配词)。
        """
        op = SuibianTempleAdventureSquad(test_context, dispatch=True)
        op.current_mission_idx = 4  # 末尾 idx(len-1)
        result = op.prepare_to_choose_mission()
        assert result.status == '已完成所有副本选择', 'idx 走完应完成所有副本选择'
        assert op.current_mission_idx == 5

    def test_prepare_to_choose_mission_next(self, test_context: TestContext) -> None:
        """dispatch=True + idx 未到末尾 → round_success(无 status,idx 自增进选副本)。

        设 ``current_mission_idx=0`` → ``+1=1 < 5`` → ``round_success()``(无 status,进入 choose_mission)。
        """
        op = SuibianTempleAdventureSquad(test_context, dispatch=True)
        op.current_mission_idx = 0
        result = op.prepare_to_choose_mission()
        assert result.is_success, 'idx 未走完应 round_success 进入选副本'
        assert not result.status, '未到末尾时无 status(进 choose_mission)'
        assert op.current_mission_idx == 1

    def test_back_to_entry_at_entry(self, test_context: TestContext) -> None:
        """随便观-入口(手动态)→ back_to_entry → round_success(已在入口)。

        ``back_to_entry`` 先 ``check_and_update_current_screen(['随便观-入口'])``,入口-手动态
        命中随便观-入口(``is_precise=true``)→ 直接 ``round_success``。复用现有 入口-手动态 fixture。
        """
        test_context.mock_screen('随便观', '入口-手动态')
        op = SuibianTempleAdventureSquad(test_context)
        op.screenshot()
        result = op.back_to_entry()
        assert result.is_success, '入口帧应识别已在随便观-入口 直接 round_success'

    def test_click_claim(self, test_context: TestContext) -> None:
        """可收获态(游历小队派遣到期,有「可收获」)→ click_claim OCR 命中 → round_success('可收获')。

        ``click_claim`` = ``round_by_ocr_and_click_by_priority(['可收获'])``,游历-可收获态
        (副本派遣到期)有「可收获」按钮 → 命中(下游 ``click_confirm`` 的 ``@node_from``)。
        """
        test_context.mock_screen('随便观', '游历-可收获')
        op = SuibianTempleAdventureSquad(test_context, claim=True, dispatch=False)
        op.screenshot()
        result = op.click_claim()
        assert result.is_success, '可收获态应 OCR 命中「可收获」'
        assert result.status == '可收获'

    def test_click_confirm(self, test_context: TestContext) -> None:
        """收获确认弹窗(游历完成结算,有「确认」)→ click_confirm OCR 命中 → round_success('确认')。

        ``click_confirm`` = ``round_by_ocr_and_click_by_priority(['确认'])``,点「可收获」后
        弹收获结算(游历完成 + 奖励 + 确认)→ 命中「确认」(收获完成 → ``execute_dispatch_1``)。
        """
        test_context.mock_screen('随便观', '游历-收获确认弹窗')
        op = SuibianTempleAdventureSquad(test_context, claim=True, dispatch=False)
        op.screenshot()
        result = op.click_confirm()
        assert result.is_success, '收获结算应 OCR 命中「确认」'
        assert result.status == '确认'
