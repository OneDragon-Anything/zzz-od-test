from test.conftest import TestContext

from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator


class TestAutoBattle:

    def test_all_valid(self, test_context: TestContext) -> None:
        """
        确保所有自动战斗配置文件无异常
        """
        config_list = get_auto_battle_op_config_list('auto_battle')
        for config in config_list:
            op = AutoBattleOperator(test_context, 'auto_battle', config.value)
            success, msg = op._init_operator()
            assert success, msg