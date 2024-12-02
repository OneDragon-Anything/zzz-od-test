import test
from zzz_od.application.ridu_weekly.ridu_weekly_app import RiduWeeklyApp


class TestRiduWeeklyApp(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_100(self):
        op = RiduWeeklyApp(self.ctx)
        screen = self.get_test_image('100.png')

        result = op.claim_score(screen)
        self.assertEqual('100', result.status)