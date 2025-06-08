import test
from one_dragon.base.screen import screen_utils


class TestGetMatchScreenName(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test(self):
        screen_map = {
            'normal_world_basic': '大世界-普通',
            'menu': '菜单',
            'menu_more': '菜单-更多功能',
            'storage_wengine': '仓库-音擎仓库',
            'storage_drive_disc': '仓库-驱动仓库',
            'drive_disc_dismantle': '仓库-驱动仓库-驱动盘拆解',
            'compendium_train': '快捷手册-训练',
            'compendium_train_2': '快捷手册-训练',
            'compendium_daily': '快捷手册-日常',
            'compendium_daily_2': '快捷手册-日常',
            'compendium_combat': '快捷手册-作战',
            'battle_menu': '战斗-菜单',
            'lost_void_entry': '迷失之地-入口',
            'lost_void_purge': '迷失之地-战线肃清',
            'lost_void_normal_world': '迷失之地-大世界',
            'lost_void_choose_common': '迷失之地-通用选择',
            'lost_void_choose_common_2': '迷失之地-通用选择',
            'lost_void_choose_common_3': '迷失之地-通用选择',
            'lost_void_bangboo_store': '迷失之地-邦布商店',
            'lost_void_choose_no_detail': '迷失之地-通用选择',
            'lost_void_choose_no_detail_2': '迷失之地-通用选择',
            'lost_void_choose_no_num': '迷失之地-通用选择',
            'lost_void_battle_result': '迷失之地-挑战结果',
            'lost_void_battle_result_fail': '迷失之地-挑战结果',
            'lost_void_battle_fail': '迷失之地-战斗失败',
        }
        self.ctx.screen_loader.update_current_screen_name('菜单')
        for image_name, screen_name in screen_map.items():
            screen = self.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(self.ctx, screen)
            self.assertEqual(screen_name, result)

        screen_name_list = [i for i in screen_map.values()]
        for image_name, screen_name in screen_map.items():
            screen = self.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(self.ctx, screen, screen_name_list=screen_name_list)
            self.assertEqual(screen_name, result)