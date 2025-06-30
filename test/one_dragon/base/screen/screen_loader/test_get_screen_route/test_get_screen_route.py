import test


class TestGetScreenRote(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_get_route(self):
        route = self.ctx.screen_loader.get_screen_route('快捷手册-训练', '快捷手册-战术')
        self.assertIsNotNone(route)
        self.assertTrue(route.can_go)