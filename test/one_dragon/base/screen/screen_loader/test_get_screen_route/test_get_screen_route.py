from test.conftest import TestContext


class TestGetScreenRote:

    def test_get_route(self, test_context: TestContext):
        route = test_context.screen_loader.get_screen_route('快捷手册-训练', '快捷手册-战术')
        assert route is not None
        assert route.can_go is True