"""体力计划卡片的材料数量选项测试。"""

import os
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from test.conftest import TestContext

from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanItem,
    ChargePlanRunModeEnum,
)
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanCard


def test_charge_plan_card_switches_to_material_count_mode(
    test_context: TestContext,
) -> None:
    """实战模拟室计划可选择目标材料、折算开关和进度。"""
    _app = QApplication.instance() or QApplication([])
    plan = ChargePlanItem(
        mission_type_name='代理人技能',
        mission_name='共鸣测试',
    )
    card = ChargePlanCard(test_context, 0, plan, MagicMock())

    assert card.run_mode_box.count() == 2
    assert card.target_material_name_box.isHidden()

    material_mode_idx = card.run_mode_box.findData(
        ChargePlanRunModeEnum.MATERIAL_COUNT.value.value
    )
    card.run_mode_box.setCurrentIndex(material_mode_idx)

    assert plan.is_material_count_plan
    assert card.run_times_input.isHidden()
    assert not card.target_material_name_box.isHidden()
    assert card.target_material_name_box.count() == 3

    card.target_material_name_box.setCurrentIndex(
        card.target_material_name_box.findData('进阶以太芯片')
    )
    card.target_material_name_box.setCurrentIndex(
        card.target_material_name_box.findData('特化以太芯片')
    )
    card.target_material_count_input.setText('100')
    card.include_synthesis_box.setCurrentIndex(
        card.include_synthesis_box.findData(True)
    )

    assert plan.target_material_name == '特化以太芯片'
    assert plan.target_material_count == 100
    assert plan.include_synthesis is True

    plan.material_counts = {'特化以太芯片': 10}
    card.init_material_count_inputs()
    assert card.current_material_count_input.text() == '10'

    card.reset_material_count_btn.click()
    assert plan.material_counts == {}
    assert card.current_material_count_input.text() == '0'


def test_charge_plan_card_hides_material_mode_for_other_categories(
    test_context: TestContext,
) -> None:
    """没有奖励材料弹窗的副本不显示材料运行方式。"""
    _app = QApplication.instance() or QApplication([])
    plan = ChargePlanItem(
        category_name='专业挑战室',
        mission_type_name='恶名狩猎',
        mission_name=None,
        run_mode=ChargePlanRunModeEnum.MATERIAL_COUNT.value.value,
    )
    card = ChargePlanCard(test_context, 0, plan, MagicMock())

    assert plan.run_mode == ChargePlanRunModeEnum.RUN_TIMES.value.value
    assert card.run_mode_box.count() == 1
    assert card.run_mode_box.isHidden()
    assert not card.run_times_input.isHidden()


def test_charge_plan_card_hides_material_mode_for_custom_template(
    test_context: TestContext,
) -> None:
    """混合奖励的自定义模板不开放按材料数量运行。"""
    _app = QApplication.instance() or QApplication([])
    plan = ChargePlanItem(
        mission_type_name='自定义模板',
        mission_name='自定义卡组1',
    )
    card = ChargePlanCard(test_context, 0, plan, MagicMock())

    assert card.run_mode_box.count() == 1
    assert card.run_mode_box.isHidden()
