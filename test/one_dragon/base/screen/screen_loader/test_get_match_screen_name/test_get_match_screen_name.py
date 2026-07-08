from test.conftest import TestContext

from one_dragon.base.screen import screen_utils


class TestGetMatchScreenName:

    def test(self, test_context: TestContext):
        screen_map = {
            'normal_world_basic.webp': '大世界-普通',
            'normal_world_basic_2.webp': '大世界-普通',
            'normal_world_investigation.webp': '大世界-勘域',
            'menu.webp': '菜单',
            'menu_more.webp': '菜单-更多功能',
            'storage_wengine.webp': '仓库-音擎仓库',
            'storage_drive_disc.webp': '仓库-驱动仓库',
            'drive_disc_dismantle.webp': '仓库-驱动仓库-驱动盘拆解',
            'compendium_train.webp': '快捷手册-训练',
            'compendium_train_2.webp': '快捷手册-训练',
            'compendium_daily.webp': '快捷手册-日常',
            'compendium_daily_2.webp': '快捷手册-日常',
            'compendium_daily_3.webp': '快捷手册-日常',
            'compendium_combat.webp': '快捷手册-作战',
            'battle_menu.webp': '战斗-菜单',
            'lost_void_entry.webp': '迷失之地-入口',
            'lost_void_purge.webp': '迷失之地-战线肃清',
            'lost_void_normal_world.webp': '迷失之地-大世界',
            'lost_void_choose_common.webp': '迷失之地-通用选择',
            'lost_void_choose_common_2.webp': '迷失之地-通用选择',
            'lost_void_choose_common_3.webp': '迷失之地-通用选择',
            'lost_void_choose_common_4.webp': '迷失之地-通用选择',
            'lost_void_bangboo_store.webp': '迷失之地-邦布商店',
            'lost_void_choose_no_detail.webp': '迷失之地-通用选择',
            'lost_void_choose_no_detail_2.webp': '迷失之地-通用选择',
            'lost_void_choose_no_num.webp': '迷失之地-通用选择',
            'lost_void_battle_result.webp': '迷失之地-挑战结果',
            'lost_void_battle_result_fail.webp': '迷失之地-挑战结果',
            'lost_void_battle_fail.webp': '迷失之地-战斗失败',
        }
        test_context.screen_loader.update_current_screen_name('菜单')
        for image_name, screen_name in screen_map.items():
            screen = test_context.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(test_context, screen)
            assert screen_name == result, image_name

        screen_name_list = [i for i in screen_map.values()]
        for image_name, screen_name in screen_map.items():
            screen = test_context.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(test_context, screen, screen_name_list=screen_name_list)
            assert screen_name == result, image_name