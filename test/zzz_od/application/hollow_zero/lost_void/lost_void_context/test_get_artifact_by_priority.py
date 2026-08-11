from test.conftest import TestContext

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import (
    LostVoidArtifactPos,
)


class TestGetArtifactByPriority:

    def test_get_artifact_by_priority_1(self, test_context: TestContext):
        """
        https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/issues/644
        确认第一个优先级可以匹配
        :return:
        """
        test_context.lost_void.load_artifact_data()
        test_context.lost_void.load_challenge_config()

        test_context.lost_void.challenge_config.update(
            'artifact_priority',
            ['星见雅 心间舞雀', '星见雅 霜月残雪', '星见雅 花间雀', '终结', '卡牌 讴歌喧响之唇', '无详情 获得鸣徽'],
            save=False
        )

        test_context.lost_void.challenge_config.update(
            'artifact_priority_2',
            ['异常·击破 混沌量杯', '通用 三相战斗陀螺', '绝境'],
            save=False
        )

        art_name_list = ['超越绝境之志', '[终结]蓄势架子鼓', '[异常·击破]万能催化剂', '[机敏]高效保险杠']
        art_list: list[LostVoidArtifactPos] = []
        for art_name in art_name_list:
            art = test_context.lost_void.get_artifact_by_full_name(art_name)
            # 函数里会按坐标去重
            min_x = 300 * len(art_list)
            max_x = min_x + 10
            pos = LostVoidArtifactPos(art, Rect(min_x, min_x, max_x, max_x))
            art_list.append(pos)

        priority_list: list[LostVoidArtifactPos] = test_context.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=False,
            consider_not_in_priority=False)
        assert 1 == len(priority_list)
        assert '[终结]蓄势架子鼓' == priority_list[0].artifact.display_name

        priority_list = test_context.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=True,
            consider_not_in_priority=False)
        assert 1 == len(priority_list)
        assert '[终结]蓄势架子鼓' == priority_list[0].artifact.display_name

        priority_list = test_context.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=True,
            consider_not_in_priority=True)
        assert 1 == len(priority_list)
        assert '[终结]蓄势架子鼓' == priority_list[0].artifact.display_name

    def test_priority_hit_ignores_abandon_list(self, test_context: TestContext):
        """
        修复：优先级规则命中时, 即使该分类在动态放弃组中, 也应正常选中。
        放弃组只应作用于兜底补位阶段, 不应否决优先级规则匹配。
        """
        test_context.lost_void.load_artifact_data()
        test_context.lost_void.load_challenge_config()

        test_context.lost_void.dynamic_priority_list = []
        test_context.lost_void.dynamic_abandon_list = ['击破']

        test_context.lost_void.challenge_config.update(
            'artifact_priority',
            ['击破'],
            save=False
        )

        art_name_list = ['[异常·击破]溶剂弹射枪', '[机敏]高效保险杠']
        art_list: list[LostVoidArtifactPos] = []
        for idx, art_name in enumerate(art_name_list):
            art = test_context.lost_void.get_artifact_by_full_name(art_name)
            assert art is not None, f'藏品数据缺失: {art_name}'
            min_x = 300 * idx
            max_x = min_x + 10
            pos = LostVoidArtifactPos(art, Rect(min_x, min_x, max_x, max_x))
            art_list.append(pos)

        priority_list = test_context.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=False,
            consider_not_in_priority=False)
        assert 1 == len(priority_list)
        assert '[异常·击破]溶剂弹射枪' == priority_list[0].artifact.display_name

    def test_abandon_list_only_for_fallback(self, test_context: TestContext):
        """
        放弃组只在兜底补位阶段生效：无优先级命中时, 先选不在放弃组的, 放弃组排最后。
        """
        test_context.lost_void.load_artifact_data()
        test_context.lost_void.load_challenge_config()

        test_context.lost_void.dynamic_priority_list = []
        test_context.lost_void.dynamic_abandon_list = ['击破']

        test_context.lost_void.challenge_config.update(
            'artifact_priority',
            ['星见雅 心间舞雀'],
            save=False
        )

        art_name_list = ['[异常·击破]溶剂弹射枪', '[机敏]高效保险杠']
        art_list: list[LostVoidArtifactPos] = []
        for idx, art_name in enumerate(art_name_list):
            art = test_context.lost_void.get_artifact_by_full_name(art_name)
            assert art is not None, f'藏品数据缺失: {art_name}'
            min_x = 300 * idx
            max_x = min_x + 10
            pos = LostVoidArtifactPos(art, Rect(min_x, min_x, max_x, max_x))
            art_list.append(pos)

        priority_list = test_context.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=False,
            consider_not_in_priority=True)
        assert 1 == len(priority_list)
        assert '[机敏]高效保险杠' == priority_list[0].artifact.display_name

    def test_battle_priority_is_level_4(self, test_context: TestContext):
        """
        六级模型：第 2 级（配置一）优先于第 4 级（战斗组）。
        配置一命中时, 即使战斗组也在, 也应先选配置一命中的藏品。
        """
        test_context.lost_void.load_artifact_data()
        test_context.lost_void.load_challenge_config()

        test_context.lost_void.dynamic_priority_list = []
        test_context.lost_void.dynamic_abandon_list = []

        test_context.lost_void.challenge_config.update(
            'artifact_priority',
            ['机敏'],
            save=False
        )
        test_context.lost_void.challenge_config.clear_artifact_priority_in_battle()
        test_context.lost_void.challenge_config.artifact_priority_in_battle.append('击破')

        art_name_list = ['[异常·击破]溶剂弹射枪', '[机敏]高效保险杠']
        art_list: list[LostVoidArtifactPos] = []
        for idx, art_name in enumerate(art_name_list):
            art = test_context.lost_void.get_artifact_by_full_name(art_name)
            assert art is not None, f'藏品数据缺失: {art_name}'
            min_x = 300 * idx
            max_x = min_x + 10
            pos = LostVoidArtifactPos(art, Rect(min_x, min_x, max_x, max_x))
            art_list.append(pos)

        priority_list = test_context.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=True,
            consider_not_in_priority=False)
        assert 1 == len(priority_list)
        assert '[机敏]高效保险杠' == priority_list[0].artifact.display_name