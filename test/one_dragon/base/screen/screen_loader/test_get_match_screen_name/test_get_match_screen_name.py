from test.conftest import TestContext

from one_dragon.base.screen import screen_utils


class TestGetMatchScreenName:

    def test(self, test_context: TestContext):
        screen_map = {
            'normal_world_basic.png': '大世界-普通',
            'menu.png': '菜单',
            'menu_more.png': '菜单-更多功能',
            'storage_wengine.png': '仓库-音擎仓库',
            'storage_drive_disc.png': '仓库-驱动仓库',
            'drive_disc_dismantle.png': '仓库-驱动仓库-驱动盘拆解',
            'compendium_train.png': '快捷手册-训练',
            'compendium_train_2.png': '快捷手册-训练',
            'compendium_daily.png': '快捷手册-日常',
            'compendium_daily_2.png': '快捷手册-日常',
            'compendium_combat.png': '快捷手册-作战',
            'battle_menu.png': '战斗-菜单',
            'lost_void_entry.png': '迷失之地-入口',
            'lost_void_purge.png': '迷失之地-战线肃清',
            'lost_void_normal_world.png': '迷失之地-大世界',
            'lost_void_choose_common.png': '迷失之地-通用选择',
            'lost_void_choose_common_2.png': '迷失之地-通用选择',
            'lost_void_choose_common_3.png': '迷失之地-通用选择',
            'lost_void_bangboo_store.png': '迷失之地-邦布商店',
            'lost_void_choose_no_detail.png': '迷失之地-通用选择',
            'lost_void_choose_no_detail_2.png': '迷失之地-通用选择',
            'lost_void_choose_no_num.png': '迷失之地-通用选择',
            'lost_void_battle_result.png': '迷失之地-挑战结果',
            'lost_void_battle_result_fail.png': '迷失之地-挑战结果',
            'lost_void_battle_fail.png': '迷失之地-战斗失败',
        }
        test_context.screen_loader.update_current_screen_name('菜单')
        for image_name, screen_name in screen_map.items():
            screen = test_context.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(test_context, screen)
            assert screen_name == result

        screen_name_list = [i for i in screen_map.values()]
        for image_name, screen_name in screen_map.items():
            screen = test_context.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(test_context, screen, screen_name_list=screen_name_list)
            assert screen_name == result