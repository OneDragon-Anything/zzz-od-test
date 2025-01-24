import test
from zzz_od.hollow_zero.event import resonium_utils


class TestResoniumUtils(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_choose_resonium_by_priority(self):
        resonium_list = [
            self.ctx.hollow.data_service.match_resonium_by_ocr_full('顽_ 强聚合徽标'),
            self.ctx.hollow.data_service.match_resonium_by_ocr_full('冻结聚合徽标'),
            self.ctx.hollow.data_service.match_resonium_by_ocr_full('能量 霓虹可乐')
        ]
        ans1 = resonium_utils.choose_resonium_by_priority(resonium_list, ['顽强', '冻结 xx'], only_priority=True)
        self.assertEqual(1, len(ans1))
        item = resonium_list[ans1[0]]
        self.assertEqual('顽强', item.category)
        self.assertEqual('聚合徽标', item.name)

        ans2 = resonium_utils.choose_resonium_by_priority(resonium_list, ['顽强', '冻结 xx'], only_priority=False)
        self.assertEqual(3, len(ans2))
        item = resonium_list[ans2[1]]
        self.assertEqual('能量', item.category)
        self.assertEqual('霓虹可乐', item.name)