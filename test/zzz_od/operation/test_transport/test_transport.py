from test.conftest import TestContext

from zzz_od.operation.map_transport import MapTransport


class TestTransport:

    def test_choose_tp(self, test_context: TestContext):
        test_context.add_mock_screenshot_by_path('street_6.png')

        op = MapTransport(test_context, '六分街', '报刊亭')
        op.screenshot()
        result = op.choose_tp()
        print(result.data)
        assert result.data == 0