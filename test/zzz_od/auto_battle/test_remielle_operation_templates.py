"""蕾米埃尔自动战斗动作模板回归测试。"""

from pathlib import Path
from typing import Any

import pytest
import yaml

_OPERATION_DIR = Path("config") / "auto_battle_operation"
_STATE_HANDLER_DIR = Path("config") / "auto_battle_state_handler"
_PROTECTION_STATES = {"自定义-动作不打断", "自定义-无视闪光"}


def _load_yaml(path: Path) -> dict[str, Any]:
    """读取一个自动战斗 YAML。"""
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    assert isinstance(data, dict)
    return data


def _load_operations(template_name: str) -> list[dict[str, Any]]:
    """读取操作模板的动作列表。"""
    data = _load_yaml(_OPERATION_DIR / f"{template_name}.sample.yml")
    operations = data.get("operations")
    assert isinstance(operations, list)
    assert all(isinstance(operation, dict) for operation in operations)
    return operations


@pytest.mark.parametrize(
    ("template_name", "button_name"),
    [
        ("蕾米埃尔-长按普攻", "按键-普通攻击"),
        ("蕾米埃尔-长按强化特殊技", "按键-特殊攻击"),
    ],
)
def test_long_press_keeps_pressing_and_releases(
    template_name: str,
    button_name: str,
) -> None:
    """长按期间持续补按，结束后必须松键并清除保护状态。"""
    operations = _load_operations(template_name)
    press_name = f"{button_name}-按下"
    release_name = f"{button_name}-松开"

    press_indexes = [
        index
        for index, operation in enumerate(operations)
        if operation.get("op_name") == press_name
    ]
    release_indexes = [
        index
        for index, operation in enumerate(operations)
        if operation.get("op_name") == release_name
    ]

    assert len(press_indexes) >= 2
    assert len(release_indexes) == 1
    release_index = release_indexes[0]
    assert release_index > press_indexes[-1]

    hold_waits = [
        float(operation["seconds"])
        for operation in operations[press_indexes[0] + 1:release_index]
        if operation.get("op_name") == "等待秒数"
    ]
    assert hold_waits
    assert max(hold_waits) <= 0.5

    protection = operations[0]
    assert protection.get("op_name") == "设置状态"
    assert set(protection.get("state_list", [])) == _PROTECTION_STATES
    protection_seconds = float(protection["seconds"])
    hold_seconds = sum(hold_waits)
    assert hold_seconds <= protection_seconds <= hold_seconds + 0.5

    clear_protection = operations[release_index + 1]
    assert clear_protection.get("op_name") == "清除状态"
    assert set(clear_protection.get("state_list", [])) == _PROTECTION_STATES


def test_switch_protection_only_covers_entry_wait() -> None:
    """普通切入保护不能远长于实际入场等待。"""
    data = _load_yaml(_STATE_HANDLER_DIR / "速切模板-蕾米埃尔.sample.yml")
    handlers = data["handlers"][0]["sub_handlers"]
    switch_handler = next(
        handler
        for handler in handlers
        if "按键-切换角色-下一个" in handler.get("states", "")
    )
    operations = switch_handler["operations"]
    protection_seconds = float(operations[0]["seconds"])
    wait_seconds = float(operations[1]["seconds"])

    assert protection_seconds <= 1
    assert wait_seconds <= protection_seconds


def test_chain_protection_matches_chain_wait() -> None:
    """连携保护时长与连携动作等待保持一致。"""
    operations = _load_operations("蕾米埃尔-连携攻击")
    protection_seconds = float(operations[0]["seconds"])
    wait_seconds = sum(
        float(operation["seconds"])
        for operation in operations
        if operation.get("op_name") == "等待秒数"
    )

    assert set(operations[0].get("state_list", [])) == _PROTECTION_STATES
    assert protection_seconds == wait_seconds
