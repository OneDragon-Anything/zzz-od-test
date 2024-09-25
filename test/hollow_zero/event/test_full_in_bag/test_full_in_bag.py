from PIL.ImageChops import screen

import test
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.full_in_bag import FullInBag
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent


class TestHollowEventUtils(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_check_event(self):
        screen = self.get_test_image('full_in_bag.png')
        result = hollow_event_utils.check_full_in_bag(self.ctx, screen)
        self.assertIsNotNone(result)

        result = hollow_event_utils.check_screen(self.ctx, screen, set())
        self.assertEqual(HollowZeroSpecialEvent.FULL_IN_BAG.value.event_name, result)

    def test_opts(self):
        op = FullInBag(self.ctx)
        self.add_mock_screenshot('full_in_bag.png')
        result = op.drop()
        self.assertTrue(result.is_success)