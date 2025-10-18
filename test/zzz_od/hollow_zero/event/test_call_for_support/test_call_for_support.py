from test.conftest import TestContext

from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.call_for_support import CallForSupport
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig


class TestCallForSupport:

    def test_no_agent(self, test_context: TestContext):
        """
        没有代理人的情况 不会识别到任何选项 因此点击的是事件文本
        """
        screen = test_context.get_test_image('no_agent.png')
        op = CallForSupport(test_context)
        result = hollow_event_utils.check_event_text_and_run(op, screen, op._handlers)
        assert '事件文本' == result.status

    def test_new_agent_pos(self, test_context: TestContext):
        test_context.withered_domain.challenge_config = HollowZeroChallengeConfig('', is_mock=True)
        test_context.withered_domain.challenge_config.target_agents = [
            AgentEnum.ZHU_YUAN.value.agent_id,
            AgentEnum.QINGYI.value.agent_id,
            AgentEnum.NICOLE.value.agent_id
        ]

        op = CallForSupport(test_context)

        # 现在是 朱鸢 来的是妮可
        assert 1 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.NICOLE.value
        )

        # 现在是 朱鸢 来的是青衣
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.QINGYI.value
        )

        # 现在是 朱鸢 来的是莱卡恩
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.LYCAON.value
        )

        # 现在是 朱鸢+妮可 来的是青衣
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.NICOLE.value, None],
            AgentEnum.QINGYI.value
        )

        # 现在是 朱鸢+妮可 来的是莱卡恩
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.NICOLE.value, None],
            AgentEnum.LYCAON.value
        )

        # 现在是 朱鸢+莱卡恩+丽娜 来的是青衣
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.LYCAON.value, AgentEnum.RINA.value],
            AgentEnum.QINGYI.value
        )

        # 现在是 朱鸢+莱卡恩+丽娜 来的是妮可
        assert 3 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.LYCAON.value, AgentEnum.RINA.value],
            AgentEnum.NICOLE.value
        )

        # 现在是 青衣 来的是朱鸢
        assert 1 == op._should_call_backup(
            [AgentEnum.QINGYI.value, None, None],
            AgentEnum.ZHU_YUAN.value
        )

        # 现在是 青衣 来的是妮可
        assert 2 == op._should_call_backup(
            [AgentEnum.QINGYI.value, None, None],
            AgentEnum.NICOLE.value
        )

        # 现在是 青衣+朱鸢 来的是妮可
        assert 2 == op._should_call_backup(
            [AgentEnum.QINGYI.value, AgentEnum.ZHU_YUAN.value, None],
            AgentEnum.NICOLE.value
        )

        # 现在是 朱鸢+青衣+妮可 来的是莱卡恩
        assert op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.QINGYI.value, AgentEnum.NICOLE.value],
            AgentEnum.LYCAON.value
        ) is None

    def test_new_agent_pos_2(self, test_context: TestContext):
        test_context.withered_domain.challenge_config = HollowZeroChallengeConfig('', is_mock=True)
        test_context.withered_domain.challenge_config.target_agents = [
            AgentEnum.ZHU_YUAN.value.agent_id,
            AgentTypeEnum.STUN.value,
            AgentEnum.NICOLE.value.agent_id
        ]

        op = CallForSupport(test_context)

        # 现在是 朱鸢 来的是妮可
        assert 1 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.NICOLE.value
        )

        # 现在是 朱鸢 来的是妮可
        assert 1 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.NICOLE.value
        )

        # 现在是 朱鸢 来的是青衣
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.QINGYI.value
        )

        # 现在是 朱鸢 来的是莱卡恩
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, None, None],
            AgentEnum.LYCAON.value
        )

        # 现在是 朱鸢+妮可 来的是青衣
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.NICOLE.value, None],
            AgentEnum.QINGYI.value
        )

        # 现在是 朱鸢+妮可 来的是莱卡恩
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.NICOLE.value, None],
            AgentEnum.LYCAON.value
        )

        # 现在是 朱鸢+莱卡恩+丽娜 来的是青衣
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.LYCAON.value, AgentEnum.RINA.value],
            AgentEnum.QINGYI.value
        )

        # 现在是 朱鸢+莱卡恩+丽娜 来的是妮可
        assert 3 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.LYCAON.value, AgentEnum.RINA.value],
            AgentEnum.NICOLE.value
        )

        # 现在是 青衣 来的是朱鸢
        assert 1 == op._should_call_backup(
            [AgentEnum.QINGYI.value, None, None],
            AgentEnum.ZHU_YUAN.value
        )

        # 现在是 青衣 来的是妮可
        assert 2 == op._should_call_backup(
            [AgentEnum.QINGYI.value, None, None],
            AgentEnum.NICOLE.value
        )

        # 现在是 青衣+朱鸢 来的是妮可
        assert 2 == op._should_call_backup(
            [AgentEnum.QINGYI.value, AgentEnum.ZHU_YUAN.value, None],
            AgentEnum.NICOLE.value
        )

        # 现在是 朱鸢+青衣+妮可 来的是莱卡恩
        assert 2 == op._should_call_backup(
            [AgentEnum.ZHU_YUAN.value, AgentEnum.QINGYI.value, AgentEnum.NICOLE.value],
            AgentEnum.LYCAON.value
        )