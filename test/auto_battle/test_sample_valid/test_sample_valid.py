import test
from zzz_od.application.battle_assistant.auto_battle_config import get_all_auto_battle_op
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator


class TestSampleValid(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_all_sample(self) -> None:
        """
        确保所有sample文件无异常
        :return:
        """
        op_list = get_all_auto_battle_op('auto_battle')
        for op_item in op_list:
            if not op_item.is_sample:
                continue
            auto = AutoBattleOperator(self.ctx, 'auto_battle', op_item.module_name)
            success, msg = auto._init_operator()
            self.assertTrue(success, msg)