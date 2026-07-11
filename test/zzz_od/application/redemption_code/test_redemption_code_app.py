"""RedemptionCodeApp 兑换码流程测试。

覆盖导航节点(菜单 → 更多 → 兑换码):
- ``open_menu``:菜单画面识别
- ``click_more``:菜单底部点「更多」
- ``click_code``:菜单-更多功能点「兑换码」

未覆盖(留标记,见模块 docstring 与 `兑换码输入.md` 备注):
- ``check_new_code``:依赖 ``run_record`` 的未用兑换码列表(配置态,非画面识别)。
- ``input_code`` / ``confirm_code``:用 ``keyboard.type`` 注入兑换码 + 需有效兑换码
  触发结果弹窗,无法离线 mock(MockController 无真实键盘注入 + 无真码),待集成测试。
- ``back``:``BackToNormalWorld`` 通用导航,由其自身测试覆盖。

fixture 图(`screens/`):`菜单/菜单.webp`、`菜单-更多功能/默认.webp`。
"""
from test.conftest import TestContext
from zzz_od.application.redemption_code.redemption_code_app import RedemptionCodeApp


class TestRedemptionCodeApp:
    """兑换码 app 导航节点测试。"""

    def _make_op(self, test_context: TestContext, screen: str, state: str) -> RedemptionCodeApp:
        test_context.mock_screen(screen, state)
        op = RedemptionCodeApp(test_context)
        op.screenshot()
        return op

    def test_open_menu(self, test_context: TestContext) -> None:
        """已到菜单 → open_menu 识别成功。"""
        op = self._make_op(test_context, '菜单', '菜单')
        result = op.open_menu()
        assert result.is_success, '应识别到菜单画面'

    def test_click_more(self, test_context: TestContext) -> None:
        """菜单 → 点底部「更多」tab。"""
        op = self._make_op(test_context, '菜单', '菜单')
        result = op.click_more()
        assert result.is_success, '应识别并点击「更多」'

    def test_click_code(self, test_context: TestContext) -> None:
        """菜单-更多功能 → 点「兑换码」。"""
        op = self._make_op(test_context, '菜单-更多功能', '默认')
        result = op.click_code()
        assert result.is_success, '应识别并点击「兑换码」'
