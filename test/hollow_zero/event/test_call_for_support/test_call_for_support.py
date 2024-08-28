import test
from zzz_od.operation.hollow_zero.event import event_utils
from zzz_od.operation.hollow_zero.event.call_for_support import CallForSupport


class TestChooseSimUniNum(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_no_agent(self):
        """
        没有代理人的情况 不会识别到任何选项 因此点击的是事件文本
        :return:
        """
        screen = self.get_test_image('no_agent.png')
        op = CallForSupport(self.ctx)
        result = event_utils.check_event_text_and_run(op, screen, op._handlers)
        self.assertEqual('事件文本', result.status)
