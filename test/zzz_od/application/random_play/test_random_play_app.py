"""RandomPlayApp 录像店营业测试。

覆盖:
- ``check_running``(识别营业状态):未营业态检测「开始营业」→ 放行走营业流程;正在营业态检测「正在营业」→ ``STATUS_ALREADY_RUNNING`` 关闭页面。
- ``wait_run``(等待经营画面加载):每日首次「昨日账本」弹窗 → 点关闭后重试,不误判为经营状况。

fixture(`screens/影像店营业/`):`经营状况-未营业.webp`、`经营状况.webp`(正在营业)、`昨日账本.webp`。
"""
from test.conftest import TestContext

from zzz_od.application.random_play.random_play_app import RandomPlayApp


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
