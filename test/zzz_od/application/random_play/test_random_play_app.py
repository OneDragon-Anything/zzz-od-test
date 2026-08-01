"""RandomPlayApp 录像店营业测试。

覆盖:
- ``check_running``(识别营业状态):未营业态检测「开始营业」→ 放行走营业流程;正在营业态检测「正在营业」→ ``STATUS_ALREADY_RUNNING`` 关闭页面。
- ``wait_run``(等待经营画面加载):每日首次「昨日账本」弹窗 → 点关闭后重试,不误判为经营状况。
- ``handle_interaction_dialog``(PR #2574 POINT_3):POINT_1 直接放行;POINT_3 选项态 OCR 点「查看经营状况」;POINT_3 阿玖旁白态盲点「对话框标题」推进。

fixture(`screens/影像店营业/`):`经营状况-未营业.webp`、`经营状况.webp`(正在营业)、`昨日账本.webp`、`查看经营状况-选项.webp`、`POINT_3-阿玖旁白.webp`。
"""
from test.conftest import TestContext

from zzz_od.application.random_play.random_play_app import RandomPlayApp
from zzz_od.application.random_play.random_play_config import RandomPlayTransportPoint


class TestRandomPlayApp:
    """录像店营业 app 测试。"""

    def _make_op(self, test_context: TestContext, state: str) -> RandomPlayApp:
        test_context.mock_screen('影像店营业', state)
        op = RandomPlayApp(test_context)
        op.screenshot()
        return op

    def test_check_running_not_running(self, test_context: TestContext) -> None:
        """未营业态(开始营业)→ check_running 放行,且不判为已营业。"""
        op = self._make_op(test_context, '经营状况-未营业')
        result = op.check_running()
        assert result.is_success, '未营业态应识别「开始营业」并放行'
        assert result.status != RandomPlayApp.STATUS_ALREADY_RUNNING, '未营业态不应判为已营业'

    def test_check_running_already_running(self, test_context: TestContext) -> None:
        """正在营业态 → check_running 返回 STATUS_ALREADY_RUNNING。"""
        op = self._make_op(test_context, '经营状况')
        result = op.check_running()
        assert result.is_success, '正在营业态应识别「正在营业」'
        assert result.status == RandomPlayApp.STATUS_ALREADY_RUNNING, '应判为已营业'

    def test_wait_run_yesterday_ledger(self, test_context: TestContext) -> None:
        """每日首次昨日账本弹窗 → wait_run 检测后点关闭并重试,不进经营状况。"""
        op = self._make_op(test_context, '昨日账本')
        result = op.wait_run()
        assert not result.is_success, '昨日账本态应点关闭后 round_retry,不应 round_success'

    def test_handle_interaction_dialog_point1(self, test_context: TestContext) -> None:
        """POINT_1(柜台)→ handle_interaction_dialog 直接放行(无选项对话)。"""
        op = self._make_op(test_context, '经营状况')  # 画面无关:POINT_1 不看对话框直接放行
        op.config.transport_point = RandomPlayTransportPoint.POINT_1.value.value
        result = op.handle_interaction_dialog()
        assert result.is_success, 'POINT_1 应直接 round_success(无选项对话)'

    def test_handle_interaction_dialog_point3_choose(self, test_context: TestContext) -> None:
        """POINT_3 选项态(查看经营状况可见)→ OCR 点「查看经营状况」→ success。"""
        op = self._make_op(test_context, '查看经营状况-选项')
        op.config.transport_point = RandomPlayTransportPoint.POINT_3.value.value
        result = op.handle_interaction_dialog()
        assert result.is_success, '选项态应 OCR 点「查看经营状况」并 success'

    def test_handle_interaction_dialog_point3_advance(self, test_context: TestContext) -> None:
        """POINT_3 阿玖旁白(无查看经营状况)→ 盲点对话框标题推进 → retry(继续对话)。"""
        op = self._make_op(test_context, 'POINT_3-阿玖旁白')
        op.config.transport_point = RandomPlayTransportPoint.POINT_3.value.value
        result = op.handle_interaction_dialog()
        assert not result.is_success, '阿玖旁白态应点对话框标题后 round_retry,不应 success'
        assert result.status == '继续对话', f'应返回「继续对话」,实际 {result.status}'

