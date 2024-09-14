import test
from zzz_od.game_data.agent import AgentEnum
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.call_for_support import CallForSupport


class TestHollowContext(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_update_agent_list_after_support(self):
        """
        呼叫增援后 更新代理人列表
        :return:
        """
        # 原有朱鸢 新增青衣在2号位
        self.ctx.hollow.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]
        self.ctx.hollow.update_agent_list_after_support(AgentEnum.QINGYI.value, 2)
        self.assertEqual(AgentEnum.ZHU_YUAN.value.agent_name, self.ctx.hollow.agent_list[0].agent_name)
        self.assertEqual(AgentEnum.QINGYI.value.agent_name, self.ctx.hollow.agent_list[1].agent_name)

        # 原有朱鸢 新增妮可在1号位
        self.ctx.hollow.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]
        self.ctx.hollow.update_agent_list_after_support(AgentEnum.NICOLE.value, 1)
        self.assertEqual(AgentEnum.NICOLE.value.agent_name, self.ctx.hollow.agent_list[0].agent_name)
        self.assertEqual(AgentEnum.ZHU_YUAN.value.agent_name, self.ctx.hollow.agent_list[1].agent_name)

        # 原有朱鸢+青衣 新增妮可在3号位
        self.ctx.hollow.agent_list = [AgentEnum.ZHU_YUAN.value, AgentEnum.QINGYI.value, None]
        self.ctx.hollow.update_agent_list_after_support(AgentEnum.NICOLE.value, 3)
        self.assertEqual(AgentEnum.ZHU_YUAN.value.agent_name, self.ctx.hollow.agent_list[0].agent_name)
        self.assertEqual(AgentEnum.QINGYI.value.agent_name, self.ctx.hollow.agent_list[1].agent_name)
        self.assertEqual(AgentEnum.NICOLE.value.agent_name, self.ctx.hollow.agent_list[2].agent_name)

        # 原有朱鸢+妮可 新增青衣在2号位
        self.ctx.hollow.agent_list = [AgentEnum.ZHU_YUAN.value, AgentEnum.NICOLE.value, None]
        self.ctx.hollow.update_agent_list_after_support(AgentEnum.QINGYI.value, 2)
        self.assertEqual(AgentEnum.ZHU_YUAN.value.agent_name, self.ctx.hollow.agent_list[0].agent_name)
        self.assertEqual(AgentEnum.QINGYI.value.agent_name, self.ctx.hollow.agent_list[1].agent_name)
        self.assertEqual(AgentEnum.NICOLE.value.agent_name, self.ctx.hollow.agent_list[2].agent_name)

        # 原有朱鸢+莱卡恩+妮可 新增青衣在2号位
        self.ctx.hollow.agent_list = [AgentEnum.ZHU_YUAN.value, AgentEnum.LYCAON.value, AgentEnum.NICOLE.value]
        self.ctx.hollow.update_agent_list_after_support(AgentEnum.QINGYI.value, 2)
        self.assertEqual(AgentEnum.ZHU_YUAN.value.agent_name, self.ctx.hollow.agent_list[0].agent_name)
        self.assertEqual(AgentEnum.QINGYI.value.agent_name, self.ctx.hollow.agent_list[1].agent_name)
        self.assertEqual(AgentEnum.NICOLE.value.agent_name, self.ctx.hollow.agent_list[2].agent_name)