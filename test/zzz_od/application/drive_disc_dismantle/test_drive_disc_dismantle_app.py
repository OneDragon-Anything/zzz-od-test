"""DriveDiscDismantleApp 驱动盘拆解测试。

覆盖核心节点(拆解画面默认态):
- ``click_filter``:点「快速选择」
- ``click_salvage``:点「拆解」

未覆盖(留标记,见 `驱动盘拆解.md` 备注):
- ``goto_salvage``:依赖 ``round_by_goto_screen`` 多画面导航。
- ``choose_level`` / ``choose_abandon``:依赖 ``config.dismantle_level`` / ``dismantle_abandon``。
- ``click_filter_confirm`` / ``click_salvage_confirm``:快速选择 / 拆解确认弹窗(子态,需选中驱动盘)。
- ``back_at_first`` / ``back_at_last``:``BackToNormalWorld`` 通用导航。

fixture(`screens/仓库-驱动仓库-驱动盘拆解/`):`默认.webp`、`快速选择.webp`。
"""
from test.conftest import TestContext
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_app import DriveDiscDismantleApp


class TestDriveDiscDismantleApp:
    """驱动盘拆解 app 核心节点测试。"""

    def _make_op(self, test_context: TestContext, state: str) -> DriveDiscDismantleApp:
        test_context.mock_screen('仓库-驱动仓库-驱动盘拆解', state)
        op = DriveDiscDismantleApp(test_context)
        op.screenshot()
        return op

    def test_click_filter(self, test_context: TestContext) -> None:
        """拆解默认态 → 点「快速选择」。"""
        op = self._make_op(test_context, '默认')
        result = op.click_filter()
        assert result.is_success, '应识别并点击「快速选择」'

    def test_click_salvage(self, test_context: TestContext) -> None:
        """拆解默认态 → 点「拆解」。"""
        op = self._make_op(test_context, '默认')
        result = op.click_salvage()
        assert result.is_success, '应识别并点击「拆解」'
