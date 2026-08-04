"""体力计划设置卡片的特训目标显示规则。"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.game_data.compendium import CompendiumService
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanCard


def test_training_goal_only_shows_runtime_settings() -> None:
    """动态计划不让用户填写运行时才能确定的副本与次数。"""
    app = QApplication.instance() or QApplication([])
    compendium_service = CompendiumService()
    compendium_service.reload()
    ctx = SimpleNamespace(
        compendium_service=compendium_service,
        team_config=SimpleNamespace(team_list=[]),
    )
    plan = ChargePlanItem(
        category_name='特训目标',
        mission_type_name='',
        mission_name=None,
        predefined_team_idx=-1,
    )
    config = MagicMock(spec=ChargePlanConfig)
    card = ChargePlanCard(ctx, 0, plan, config)

    card.show()
    app.processEvents()

    assert card.category_combo_box.currentData() == '特训目标'
    assert not card.mission_type_combo_box.isVisible()
    assert not card.mission_combo_box.isVisible()
    assert not card.card_num_box.isVisible()
    assert not card.run_times_input.isVisible()
    assert not card.plan_times_input.isVisible()
    assert card.predefined_team_opt.isVisible()
    assert card.auto_battle_combo_box.isVisible()

    card.close()
