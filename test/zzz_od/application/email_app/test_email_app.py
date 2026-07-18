"""EmailApp 邮件领取测试。

覆盖两个场景(核心分支):
- **有可领附件**:列表态(附件格有道具)→ 全部领取 → 确认弹窗 → 确认。
- **无可领附件**:列表态(附件格全 ``EMPTY``)→ 全部领取(灰色也能识别点击)
  → 无确认弹窗 → 确认节点找不到「确认」→ 走 ``@node_from(success=False)`` 分支返回。

fixture 图(`screens/邮件/`):
- ``列表.webp``:无可领列表态(附件格全 EMPTY)。
- ``列表-有可领.webp``:有可领列表态(附件格有道具)。
- ``确认弹窗.webp``:领取后弹出的「获得 XX」模态弹窗。

节点方法直接调(参照 ``test_ridu_weekly_app`` 惯例):mock 一帧 → ``op.screenshot()``
取帧到 ``last_screenshot`` → 调节点 → 断言 ``OperationRoundResult``。
"""
from test.conftest import TestContext
from zzz_od.application.email_app.email_app import EmailApp


class TestEmailApp:
    """EmailApp 邮件领取节点测试(有/无可领两场景)。"""

    def _make_op(self, test_context: TestContext, state: str) -> EmailApp:
        """mock 邮件画面某子态并取帧,返回已就绪的 EmailApp。"""
        test_context.mock_screen('邮件', state)
        op = EmailApp(test_context)
        op.screenshot()
        return op

    def test_goto_email(self, test_context: TestContext) -> None:
        """已到邮件画面 → goto_email 识别成功。"""
        op = self._make_op(test_context, '列表')
        result = op.goto_email()
        assert result.is_success, '应识别到邮件画面'

    def test_click_get_all_with_rewards(self, test_context: TestContext) -> None:
        """有可领列表态 → 全部领取可识别并点击。"""
        op = self._make_op(test_context, '列表-有可领')
        result = op.click_get_all()
        assert result.is_success, '应识别并点击「全部领取」'

    def test_click_get_all_without_rewards(self, test_context: TestContext) -> None:
        """无可领列表态 → 「全部领取」按钮(灰色)仍能识别点击。"""
        op = self._make_op(test_context, '列表')
        result = op.click_get_all()
        assert result.is_success, '全部领取灰色也应识别(EmailApp 注释:灰色也能识别到)'

    def test_click_confirm_with_dialog(self, test_context: TestContext) -> None:
        """确认弹窗 → 点确认(有可领、领取后弹出)。"""
        op = self._make_op(test_context, '确认弹窗')
        result = op.click_confirm()
        assert result.is_success, '应在弹窗识别并点击「确认」'

    def test_click_confirm_without_dialog(self, test_context: TestContext) -> None:
        """无可领列表态(无确认弹窗)→ 找不到「确认」→ 不成功(走失败分支返回)。"""
        op = self._make_op(test_context, '列表')
        result = op.click_confirm()
        assert not result.is_success, '无弹窗时确认节点不应成功'
