import test
from zzz_od.operation.transport import Transport


class TestTransport(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_choose_tp(self):
        self.add_mock_screenshot('street_6')

        op = Transport(self.ctx, '六分街', '报刊亭')
        result = op.choose_tp()
        print(result.data)
        self.assertTrue(result.data == 0)