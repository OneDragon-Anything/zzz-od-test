from test.conftest import TestContext

from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.full_in_bag import FullInBag
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent


class TestHollowEventUtils:

    def test_check_event(self, test_context: TestContext):
        screen = test_context.get_test_image('full_in_bag.png')
        result = hollow_event_utils.check_full_in_bag(test_context, screen)
        assert result is not None

        result = hollow_event_utils.check_screen(test_context, screen, set())
        assert HollowZeroSpecialEvent.FULL_IN_BAG.value.event_name == result

    def test_opts(self, test_context: TestContext):
        op = FullInBag(test_context)
        test_context.add_mock_screenshot_by_path('full_in_bag.png')
        op.screenshot()
        result = op.drop()
        assert result.is_success is True