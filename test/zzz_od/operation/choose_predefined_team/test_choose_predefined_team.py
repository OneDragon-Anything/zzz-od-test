from pathlib import Path
from typing import Any

import pytest
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import cv2_utils
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam

SCREEN_ROOT = Path(__file__).resolve().parents[4] / 'screens'


def load_screen(screen_name: str, state: str) -> MatLike:
    """读取预备编队流程的画面存档。"""
    image = cv2_utils.read_image(str(SCREEN_ROOT / screen_name / f'{state}.webp'))
    assert image is not None
    return image


@pytest.fixture
def operation(test_context: Any) -> ChoosePredefinedTeam:
    """创建只用于调用公共画面区域接口的选队操作。"""
    return ChoosePredefinedTeam(test_context, [])


def get_predefined_deploy_area(test_context: Any) -> ScreenArea:
    """获取所有选队状态机共用的预备出战区域。"""
    area = test_context.screen_loader.get_area('实战模拟室', '预备出战')
    assert area is not None
    return area


def test_predefined_deploy_uses_exact_white_text(test_context: Any) -> None:
    """预备出战区域必须完整匹配白色启用文字。"""
    area = get_predefined_deploy_area(test_context)

    assert area.text == '预备出战'
    assert area.lcs_percent == 1.0
    assert area.color_range == [[240, 240, 240], [255, 255, 255]]


def test_predefined_deploy_accepts_enabled_button(
        test_context: Any,
        monkeypatch: pytest.MonkeyPatch,
        operation: ChoosePredefinedTeam,
) -> None:
    """白色启用按钮应能通过公共区域接口完成点击。"""
    clicked_points: list[Point] = []

    def record_click(
            pos: Point | None = None,
            press_time: float = 0,
            pc_alt: bool = False,
            gamepad_key: str | None = None,
    ) -> bool:
        """记录公共区域接口发出的点击位置。"""
        if pos is not None:
            clicked_points.append(pos)
        return True

    monkeypatch.setattr(test_context.controller, 'click', record_click)
    screen = load_screen('预备编队', '已选择')

    result = operation.round_by_find_and_click_area(
        screen,
        '实战模拟室',
        '预备出战',
    )

    assert result.is_success
    assert clicked_points


@pytest.mark.parametrize(
    ('screen_name', 'state'),
    [
        ('预备编队', '未选择'),
        ('实战模拟室', '出战编队'),
    ],
)
def test_predefined_deploy_rejects_unavailable_text(
        test_context: Any,
        monkeypatch: pytest.MonkeyPatch,
        operation: ChoosePredefinedTeam,
        screen_name: str,
        state: str,
) -> None:
    """灰色禁用按钮和部分相似文字都不得触发点击。"""
    def unexpected_click(
            pos: Point | None = None,
            press_time: float = 0,
            pc_alt: bool = False,
            gamepad_key: str | None = None,
    ) -> bool:
        """在不可用画面触发点击时立即让测试失败。"""
        raise AssertionError(f'不可用的预备出战不应被点击: {pos}')

    monkeypatch.setattr(test_context.controller, 'click', unexpected_click)
    screen = load_screen(screen_name, state)

    result = operation.round_by_find_and_click_area(
        screen,
        '实战模拟室',
        '预备出战',
    )

    assert result.result == OperationRoundResultEnum.RETRY
