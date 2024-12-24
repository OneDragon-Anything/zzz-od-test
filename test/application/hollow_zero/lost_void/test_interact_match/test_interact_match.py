import test
from one_dragon.base.screen import screen_utils


class TestInteractMatch(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test(self):
        screen = self.get_test_image('2.png')
        mrl = self.ctx.tm.match_template(screen, 'lost_void_common', 'exclamation_point', only_best=False, threshold=0.7)
        self.assertEqual(2, len(mrl))

        'battlefront_purge'