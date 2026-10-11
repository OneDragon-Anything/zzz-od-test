import numpy as np
from test.conftest import TestContext

from one_dragon.base.screen import screen_utils


class TestGetMatchScreenName:

    def test_compendium_tab_with_brighter_yellow(
        self,
        test_context: TestContext,
    ) -> None:
        """选中卡片的黄色偏亮时，仍应识别实际选中的目标 TAB。"""
        screen = test_context.load_screen('快捷手册', '目标TAB').copy()
        area = test_context.screen_loader.get_area('快捷手册', 'TAB列表')
        tab_image = screen[
            area.rect.y1:area.rect.y2,
            area.rect.x1:area.rect.x2,
        ]
        rgb = tab_image.astype(np.int16)
        yellow = (
            (rgb[:, :, 0] > 170)
            & (rgb[:, :, 1] > 140)
            & (rgb[:, :, 2] < 100)
            & (rgb[:, :, 0] - rgb[:, :, 2] > 90)
        )
        green = rgb[:, :, 1]
        # 旧配置的绿色通道上界是 210；加 10 即可稳定复现颜色过滤后 OCR 为空。
        tab_image[:, :, 1] = np.where(
            yellow,
            np.clip(green + 10, 0, 255),
            green,
        ).astype(np.uint8)

        previous_current = test_context.screen_loader.current_screen_name
        previous_last = test_context.screen_loader.last_screen_name
        try:
            test_context.screen_loader.current_screen_name = '快捷手册-训练'
            test_context.screen_loader.last_screen_name = '大世界-普通'
            result = screen_utils.get_match_screen_name(test_context, screen)
        finally:
            test_context.screen_loader.current_screen_name = previous_current
            test_context.screen_loader.last_screen_name = previous_last

        assert result == '快捷手册-目标'

    def test_compendium_combat_is_not_tactics(
        self,
        test_context: TestContext,
    ) -> None:
        """“作战”和“战术”只共享一个字，不能互相判定为命中。"""
        screen = test_context.load_screen('快捷手册', '作战TAB')

        assert screen_utils.is_target_screen(
            test_context,
            screen,
            screen_name='快捷手册-作战',
        )
        assert not screen_utils.is_target_screen(
            test_context,
            screen,
            screen_name='快捷手册-战术',
        )

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
            'lost_void_entry_periodic.webp': '迷失之地-入口-周期',
            'lost_void_entry_standard.webp': '迷失之地-入口-常规',
            'lost_void_entry_purge.webp': '迷失之地-战线肃清',
            'lost_void_entry_task_force.webp': '迷失之地-特遣调查',
            'lost_void_entry_matrix_action.webp': '迷失之地-矩阵行动',
            'lost_void_entry_matrix_action_team_select.webp': '迷失之地-矩阵行动-编队选择',
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

        screen_name_list = list(screen_map.values())
        for image_name, screen_name in screen_map.items():
            screen = test_context.get_test_image(image_name)
            result = screen_utils.get_match_screen_name(test_context, screen, screen_name_list=screen_name_list)
            assert screen_name == result, image_name
