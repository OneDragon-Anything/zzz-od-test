import test
from one_dragon.base.matcher.match_result import MatchResult


class TestLostVoidContext(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_get_artifact_by_priority_1(self):
        """
        https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/issues/644
        确认第一个优先级可以匹配
        :return:
        """
        self.ctx.lost_void.load_artifact_data()
        self.ctx.lost_void.load_challenge_config()

        self.ctx.lost_void.challenge_config.update(
            'artifact_priority',
            ['星见雅 心间舞雀', '星见雅 霜月残雪', '星见雅 花间雀', '终结', '卡牌 讴歌喧响之唇', '无详情 获得鸣徽'],
            save=False
        )

        self.ctx.lost_void.challenge_config.update(
            'artifact_priority_2',
            ['异常·击破 混沌量杯', '通用三相战斗陀螺', '绝境'],
            save=False
        )

        art_name_list = ['卡牌 超越绝境之志', '终结 蓄势架子鼓', '异常·击破 万能催化剂', '机敏 高效保险杠']
        art_list = []
        for art_name in art_name_list:
            art = self.ctx.lost_void.match_artifact_by_ocr_full(art_name)
            mr = MatchResult(1, 0, 0, 0, 0, data=art)
            art_list.append(mr)

        priority_list = self.ctx.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=False,
            consider_not_in_priority=False)
        self.assertEqual(1, len(priority_list))
        self.assertEqual('终结 蓄势架子鼓', priority_list[0].data.display_name)

        priority_list = self.ctx.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=True,
            consider_not_in_priority=False)
        self.assertEqual(1, len(priority_list))
        self.assertEqual('终结 蓄势架子鼓', priority_list[0].data.display_name)

        priority_list = self.ctx.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=True,
            consider_not_in_priority=True)
        self.assertEqual(1, len(priority_list))
        self.assertEqual('终结 蓄势架子鼓', priority_list[0].data.display_name)