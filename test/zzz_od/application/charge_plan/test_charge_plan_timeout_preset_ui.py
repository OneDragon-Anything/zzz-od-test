from collections.abc import Callable
from dataclasses import dataclass

import pytest

from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.gui.view.one_dragon.charge_plan_interface import (
    ChargePlanCard,
    DoubleRewardEventConfigCard,
)


class _FakeWidget:

    def __init__(self) -> None:
        self.visible: bool = True

    def setVisible(self, visible: bool) -> None:
        self.visible = visible


class _FakeButton(_FakeWidget):

    def __init__(self) -> None:
        super().__init__()
        self.text: str = ''

    def setText(self, text: str) -> None:
        self.text = text


class _FakeSpinBox(_FakeWidget):

    def __init__(self, callback: Callable[[int], None] | None = None) -> None:
        super().__init__()
        self.value: int = 0
        self.signals_blocked: bool = False
        self.callback: Callable[[int], None] | None = callback

    def blockSignals(self, blocked: bool) -> None:
        self.signals_blocked = blocked

    def setValue(self, value: int) -> None:
        self.value = value
        if not self.signals_blocked and self.callback is not None:
            self.callback(value)


@dataclass
class _CardHarness:
    plan: ChargePlanItem
    battle_timeout_input: _FakeSpinBox
    battle_timeout_label: _FakeWidget
    battle_timeout_preset_btn: _FakeButton
    emitted: bool = False

    def _emit_value(self) -> None:
        self.emitted = True


def _new_harness(category_name: str, timeout_seconds: int) -> _CardHarness:
    harness = _CardHarness(
        plan=ChargePlanItem(
            category_name=category_name,
            battle_timeout_seconds=timeout_seconds,
        ),
        battle_timeout_input=_FakeSpinBox(),
        battle_timeout_label=_FakeWidget(),
        battle_timeout_preset_btn=_FakeButton(),
    )
    return harness


@pytest.mark.parametrize(
    ('card_class', 'category_name', 'preset_seconds'),
    [
        (ChargePlanCard, '实战模拟室', 120),
        (DoubleRewardEventConfigCard, '专业挑战室', 180),
    ],
)
def test_timeout_preset_keeps_custom_value_until_clicked(
    card_class: type[ChargePlanCard] | type[DoubleRewardEventConfigCard],
    category_name: str,
    preset_seconds: int,
) -> None:
    harness = _new_harness(category_name, timeout_seconds=60)

    card_class.init_battle_timeout_input(harness)

    assert harness.plan.battle_timeout_seconds == 60
    assert harness.battle_timeout_input.value == 60
    assert harness.battle_timeout_preset_btn.text == f'S级时限 {preset_seconds} 秒'
    assert harness.battle_timeout_preset_btn.visible is True

    harness.battle_timeout_input.callback = lambda value: card_class._on_battle_timeout_changed(harness, value)
    card_class._on_battle_timeout_preset_clicked(harness)

    assert harness.plan.battle_timeout_seconds == preset_seconds
    assert harness.emitted is True


def test_timeout_preset_is_hidden_for_unknown_category() -> None:
    harness = _new_harness('合成电池', timeout_seconds=60)

    ChargePlanCard.init_battle_timeout_input(harness)

    assert harness.plan.battle_timeout_seconds == 60
    assert harness.battle_timeout_input.value == 60
    assert harness.battle_timeout_label.visible is False
    assert harness.battle_timeout_input.visible is False
    assert harness.battle_timeout_preset_btn.visible is False


def test_category_change_updates_preset_without_overwriting_custom_value() -> None:
    harness = _new_harness('实战模拟室', timeout_seconds=60)
    ChargePlanCard.init_battle_timeout_input(harness)

    harness.plan.category_name = '专业挑战室'
    ChargePlanCard.init_battle_timeout_input(harness)

    assert harness.plan.battle_timeout_seconds == 60
    assert harness.battle_timeout_input.value == 60
    assert harness.battle_timeout_preset_btn.text == 'S级时限 180 秒'
