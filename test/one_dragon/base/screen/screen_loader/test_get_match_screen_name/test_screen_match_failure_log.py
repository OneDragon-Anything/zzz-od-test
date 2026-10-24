import pytest
from test.conftest import TestContext

from one_dragon.base.screen import screen_utils
from one_dragon.utils.log_utils import log


class TestScreenMatchFailureLog:

    @pytest.fixture(autouse=True)
    def _reset_failure_throttle(self, test_context: TestContext):
        """重置失败日志节流状态，避免测试间相互干扰（screen_loader 是 session 级共享的）。"""
        test_context.screen_loader.last_screen_match_failure_detail = None
        yield
        test_context.screen_loader.last_screen_match_failure_detail = None

    def test_match_failure_logs_color_filter_detail(
        self,
        test_context: TestContext,
        monkeypatch,
    ):
        """画面识别失败时，日志应明确列出未命中的标识特征，带颜色过滤的要标注出来。

        快捷手册-训练 靠识别高亮 TAB 的橙黄色「训练」文字（TAB-训练 带 color_range）作为画面标识，
        用菜单截图去匹配它时必然失败；失败日志应出现 `快捷手册-训练` 和 `颜色过滤`，
        便于用户一眼看出是快捷手册颜色过滤识别失败（本 issue 的核心诉求）。
        """
        captured: list[tuple] = []
        monkeypatch.setattr(log, 'warning', lambda *args, **kwargs: captured.append(args))

        screen = test_context.get_test_image('menu.webp')
        result = screen_utils.get_match_screen_name(
            test_context,
            screen,
            screen_name_list=['快捷手册-训练'],
        )

        assert result is None
        assert captured, '识别失败时应输出一条诊断 warning 日志'
        message = captured[0][0] % captured[0][1:]
        assert '快捷手册-训练' in message
        assert '颜色过滤' in message

    def test_match_failure_detail_has_no_color_filter(
        self,
        test_context: TestContext,
        monkeypatch,
    ):
        """不带 color_range 的画面标识失败时，日志只列画面与区域，不误标颜色过滤。

        用菜单截图匹配「菜单-更多功能」（该画面的标识区域无 color_range），
        失败日志应包含 `菜单-更多功能` 但不含 `颜色过滤`。
        """
        captured: list[tuple] = []
        monkeypatch.setattr(log, 'warning', lambda *args, **kwargs: captured.append(args))

        screen = test_context.get_test_image('menu.webp')
        result = screen_utils.get_match_screen_name(
            test_context,
            screen,
            screen_name_list=['菜单-更多功能'],
        )

        assert result is None
        assert captured, '识别失败时应输出一条诊断 warning 日志'
        message = captured[0][0] % captured[0][1:]
        assert '菜单-更多功能' in message
        assert '颜色过滤' not in message

    def test_match_failure_without_id_mark_logs_generic(
        self,
        test_context: TestContext,
        monkeypatch,
    ):
        """候选画面没有 id_mark（如快捷手册主画面）导致匹配失败时，也输出通用识别失败日志，不静默。"""
        captured: list[tuple] = []
        monkeypatch.setattr(log, 'warning', lambda *args, **kwargs: captured.append(args))

        screen = test_context.get_test_image('menu.webp')
        result = screen_utils.get_match_screen_name(
            test_context,
            screen,
            screen_name_list=['快捷手册'],
        )

        assert result is None
        assert captured, '识别失败时即使无接近匹配画面也应输出通用日志'
        message = captured[0][0] % captured[0][1:]
        assert '未能识别当前画面' in message

    def test_match_success_no_failure_log(
        self,
        test_context: TestContext,
        monkeypatch,
    ):
        """识别成功时不应输出识别失败的诊断日志（不打扰正常流程）。"""
        captured: list[tuple] = []
        monkeypatch.setattr(log, 'warning', lambda *args, **kwargs: captured.append(args))

        screen = test_context.get_test_image('compendium_train.webp')
        result = screen_utils.get_match_screen_name(
            test_context,
            screen,
            screen_name_list=['快捷手册-训练'],
        )

        assert result == '快捷手册-训练'
        assert not captured

    def test_match_failure_log_throttled(
        self,
        test_context: TestContext,
        monkeypatch,
    ):
        """同一失败详情只打一次日志（节流）；识别成功后重置，下次失败再打。"""
        captured: list[tuple] = []
        monkeypatch.setattr(log, 'warning', lambda *args, **kwargs: captured.append(args))

        fail_screen = test_context.get_test_image('menu.webp')
        success_screen = test_context.get_test_image('compendium_train.webp')

        # 第 1 次失败 → 输出诊断日志
        screen_utils.get_match_screen_name(test_context, fail_screen, screen_name_list=['快捷手册-训练'])
        assert len(captured) == 1, '首次识别失败应输出诊断日志'
        # 第 2 次同详情失败 → 节流不重复输出
        screen_utils.get_match_screen_name(test_context, fail_screen, screen_name_list=['快捷手册-训练'])
        assert len(captured) == 1, '同一失败详情不应重复输出日志'
        # 识别成功 → 重置节流
        screen_utils.get_match_screen_name(test_context, success_screen, screen_name_list=['快捷手册-训练'])
        # 再次失败 → 重新输出诊断日志
        screen_utils.get_match_screen_name(test_context, fail_screen, screen_name_list=['快捷手册-训练'])
        assert len(captured) == 2, '识别成功重置节流后，再次失败应重新输出日志'
