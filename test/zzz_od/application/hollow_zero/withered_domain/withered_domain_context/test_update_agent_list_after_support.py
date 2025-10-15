from test.conftest import TestContext

from zzz_od.game_data.agent import AgentEnum


class TestUpdateAgentListAfterSupport:

    def test_add_agent_to_empty_position(self, test_context: TestContext):
        """测试将代理人添加到空位置"""
        test_context.withered_domain.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[1] == AgentEnum.QINGYI.value
        assert test_context.withered_domain.agent_list[2] is None

    def test_replace_agent_at_position_1_with_empty_slot_available(
        self, test_context: TestContext
    ):
        """测试在1号位替换代理人有空位可用的情况"""
        test_context.withered_domain.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.NICOLE.value, 1
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.NICOLE.value
        assert test_context.withered_domain.agent_list[1] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[2] is None

    def test_add_agent_to_position_3_with_empty_slot(self, test_context: TestContext):
        """测试将代理人添加到3号位（有空位）"""
        test_context.withered_domain.agent_list = [
            AgentEnum.ZHU_YUAN.value,
            AgentEnum.QINGYI.value,
            None,
        ]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.NICOLE.value, 3
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[1] == AgentEnum.QINGYI.value
        assert test_context.withered_domain.agent_list[2] == AgentEnum.NICOLE.value

    def test_replace_agent_at_position_2_with_empty_slot_available(
        self, test_context: TestContext
    ):
        """测试在2号位替换代理人有空位可用的情况"""
        test_context.withered_domain.agent_list = [
            AgentEnum.ZHU_YUAN.value,
            AgentEnum.NICOLE.value,
            None,
        ]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[1] == AgentEnum.QINGYI.value
        assert test_context.withered_domain.agent_list[2] == AgentEnum.NICOLE.value

    def test_replace_agent_at_position_2_with_no_empty_slots(
        self, test_context: TestContext
    ):
        """测试在2号位替换代理人没有空位的情况"""
        test_context.withered_domain.agent_list = [
            AgentEnum.ZHU_YUAN.value,
            AgentEnum.LYCAON.value,
            AgentEnum.NICOLE.value,
        ]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[1] == AgentEnum.QINGYI.value
        assert test_context.withered_domain.agent_list[2] == AgentEnum.NICOLE.value

    def test_none_agent_list_no_change(self, test_context: TestContext):
        """测试agent_list为None时无变化"""
        test_context.withered_domain.agent_list = None

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert test_context.withered_domain.agent_list is None

    def test_invalid_position_greater_than_list_length(self, test_context: TestContext):
        """测试位置超出列表长度时无变化"""
        test_context.withered_domain.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 5
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[1] is None
        assert test_context.withered_domain.agent_list[2] is None

    def test_multiple_empty_slots_replacement_logic(self, test_context: TestContext):
        """测试多个空位时的替换逻辑"""
        test_context.withered_domain.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        # 替换1号位，原有角色应该移动到第一个空位（2号位）
        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.NICOLE.value, 1
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.NICOLE.value
        assert test_context.withered_domain.agent_list[1] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[2] is None

    def test_full_team_replacement_middle_position(self, test_context: TestContext):
        """测试满编队伍时替换中间位置"""
        test_context.withered_domain.agent_list = [
            AgentEnum.ANBY.value,
            AgentEnum.BILLY.value,
            AgentEnum.NICOLE.value,
        ]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.ZHU_YUAN.value, 2
        )

        assert test_context.withered_domain.agent_list[0] == AgentEnum.ANBY.value
        assert test_context.withered_domain.agent_list[1] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[2] == AgentEnum.NICOLE.value

    def test_edge_case_position_zero(self, test_context: TestContext):
        """测试位置为0的边界情况"""
        test_context.withered_domain.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        test_context.withered_domain.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 0
        )

        # 位置0会导致idx=-1，访问最后一个元素。因为位置为空，直接赋值
        assert test_context.withered_domain.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert test_context.withered_domain.agent_list[1] is None
        assert test_context.withered_domain.agent_list[2] is None
