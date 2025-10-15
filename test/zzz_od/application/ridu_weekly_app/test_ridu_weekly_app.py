from test.conftest import TestContext
from zzz_od.application.ridu_weekly.ridu_weekly_app import RiduWeeklyApp


class TestRiduWeeklyApp:

    def test_100(self, test_context: TestContext):
        op = RiduWeeklyApp(test_context)
        screen = test_context.get_test_image('100.png')

        result = op.claim_score(screen)
        assert '100' == result.status