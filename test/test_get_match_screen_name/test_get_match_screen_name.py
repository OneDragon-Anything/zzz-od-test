import test
from one_dragon.base.screen import screen_utils


class TestGetMatchScreenName(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test(self):
        screen_map = {
            'normal_world_basic': '大世界-普通',
            'menu': '菜单',
            'storage_wengine': '仓库-音擎仓库',
            'storage_drive_disc': '仓库-驱动仓库',
            'drive_disc_dismantle': '仓库-驱动仓库-驱动盘拆解',
            'compendium_train': '快捷手册-训练'
        }
        for image_name, screen_name in screen_map.items():
            screen = self.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(self.ctx, screen)
            self.assertEqual(screen_name, result)