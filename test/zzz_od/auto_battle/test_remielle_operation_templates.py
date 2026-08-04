from pathlib import Path

import pytest
import yaml

_OPERATION_DIR = Path("config") / "auto_battle_operation"
_PROTECTION_STATES = {"自定义-动作不打断", "自定义-无视闪光"}


def _load_operations(template_name: str) -> list[dict[str, object]]:
    path = _OPERATION_DIR / f"{template_name}.sample.yml"
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data["operations"]


@pytest.mark.parametrize(
    ("template_name", "op_prefix", "opposite_prefix"),
    [
        ("蕾米埃尔-长按普攻", "按键-普通攻击", "按键-特殊攻击"),
        ("蕾米埃尔-长按强化特殊技", "按键-特殊攻击", "按键-普通攻击"),
    ],
)
def test_remielle_long_press_keeps_protection_and_releases_key(
    template_name: str,
    op_prefix: str,
    opposite_prefix: str,
) -> None:
    """长按期间续按并最终松键，同时保留原有十秒保护。"""
    operations = _load_operations(template_name)

    protection = operations[0]
    assert set(protection["state_list"]) == _PROTECTION_STATES
    assert protection["seconds"] == 10
    assert operations[1]["op_name"] == f"{opposite_prefix}-松开"
    assert operations[2] == {"op_name": "等待秒数", "seconds": 0.02}

    hold_operations = operations[3:]
    expected_hold_operations: list[dict[str, object]] = []
    for _ in range(11):
        expected_hold_operations.extend(
            [
                {"op_name": f"{op_prefix}-按下"},
                {"op_name": "等待秒数", "seconds": 0.5},
            ]
        )
    expected_hold_operations.append({"op_name": f"{op_prefix}-松开"})

    assert hold_operations == expected_hold_operations
