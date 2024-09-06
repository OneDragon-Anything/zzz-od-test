import test
from zzz_od.game_data.agent import AgentEnum
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig
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

    def test_new_agent_pos(self):
        self.ctx.hollow_zero_challenge_config = HollowZeroChallengeConfig('', is_mock=True)
        self.ctx.hollow_zero_challenge_config.target_agents = [
            AgentEnum.ZHU_YUAN.value.agent_id,
            AgentEnum.QINGYI.value.agent_id,
            AgentEnum.NICOLE.value.agent_id
        ]

        op = CallForSupport(self.ctx)

        # 现在是 朱鸢 来的是妮可
        self.assertEqual(2, op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.NICOLE.value
        ))

        # 现在是 朱鸢+妮可 来的是青衣
        self.assertEqual(2, op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.NICOLE.value, None],
            AgentEnum.QINGYI.value
        ))

        # 现在是 朱鸢+妮可 来的是莱卡恩
        self.assertEqual(2, op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.NICOLE.value, None],
            AgentEnum.LYCAON.value
        ))

        # 现在是 朱鸢+莱卡恩+丽娜 来的是青衣
        self.assertEqual(2, op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.LYCAON.value, AgentEnum.RINA.value],
            AgentEnum.QINGYI.value
        ))

        # 现在是 朱鸢+莱卡恩+丽娜 来的是妮可
        self.assertEqual(3, op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.LYCAON.value, AgentEnum.RINA.value],
            AgentEnum.NICOLE.value
        ))

        # 现在是 青衣 来的是朱鸢
        self.assertEqual(2, op._should_call_backup(
            [AgentEnum.QINGYI.value, None, None],
            AgentEnum.ZHU_YUAN.value
        ))

        # 现在是 青衣+朱鸢 来的是妮可
        self.assertEqual(2, op._should_call_backup(
            [AgentEnum.QINGYI.value, AgentEnum.ZHU_YUAN.value, None],
            AgentEnum.NICOLE.value
        ))

