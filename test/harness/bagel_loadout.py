from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import cv2
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)
from zzz_od.application.bagel.bagel_clear_loadout import (
    LOADOUT_GROUPS,
    BagelClearLoadout,
)
from zzz_od.application.bagel.bagel_store_carried import BagelStoreCarried

if TYPE_CHECKING:
    from collections.abc import Iterator

    from cv2.typing import MatLike

    from one_dragon.base.geometry.point import Point
    from one_dragon.base.operation.operation import Operation
    from test.conftest import TestContext


class TransferController(FixtureController):
    """备战物品在同一槽位快速双击后转存；仓库使用批量按钮。"""

    def __init__(self, ctx: TestContext) -> None:
        """保留实际截图与真实 OCR，替换游戏输入。"""
        super().__init__(ctx)
        self.recorded_scrolls: list[int] = []

    @property
    def current_frame(self) -> MatLike:
        """支持明确标注的合成中间帧。"""
        frame = self._phases[self.phase_idx]['frame']
        return self.ctx.load_screen(*frame) if isinstance(frame, tuple) else frame

    def set_phases(self, phases: list[dict]) -> None:
        """把逐件转存展开为同一物品的两次点击，中间显示详情。"""
        expanded: list[dict] = []
        for phase in phases:
            spec = phase.get('exit')
            if spec and spec[0] == 'transfer':
                source = spec[1]
                screen = phase['frame']
                if isinstance(screen, tuple):
                    screen = self.ctx.load_screen(*screen)
                detail = detail_frame(self.ctx, screen, source)
                expanded.append({'frame': screen, 'exit': ('single', source)})
                expanded.append({'frame': detail, 'exit': ('single', source)})
            else:
                expanded.append(phase)
        super().set_phases(expanded)

    def click(
        self, pos: Point | None = None, press_time: float = 0,
        pc_alt: bool = False, gamepad_key: str | None = None,
    ) -> bool:
        """每个阶段只允许点击指定槽位，避免双击第二下误点菜单。"""
        spec = self._current_exit()
        if spec and spec[0] == 'single':
            assert pos is not None
            target = spec[1]
            assert abs(pos.x - target.x) <= 12 and abs(pos.y - target.y) <= 12
            assert press_time == 0.08
            self.recorded_clicks.append(pos)
            self._advance_phase()
            return True
        return super().click(pos, press_time, pc_alt, gamepad_key)

    def scroll(self, down: int, pos: Point | None = None) -> None:
        """滚动只允许发生在左侧背包内部。"""
        assert pos is not None and pos.x < 900
        self.recorded_scrolls.append(down)


class WatchedClear(WatchdogOperationMixin, BagelClearLoadout):
    """完整清空超出有限轮数立即报错。"""

    watchdog_max_rounds: int = 100


class WatchedStore(WatchdogOperationMixin, BagelStoreCarried):
    """无进展转存不能无限循环。"""

    watchdog_max_rounds: int = 65


@pytest.fixture
def controller(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, no_round_wait: None,
) -> TransferController:
    """仅替换输入；文字和槽位始终用真实识别。"""
    result = TransferController(test_context)
    monkeypatch.setattr(test_context, 'controller', result)
    return result


def paint_count(
    ctx: TestContext, screen: MatLike, screen_name: str, area_name: str, text: str,
) -> None:
    """合成数量变化，保留原截图布局及其余 OCR 内容。"""
    rect = ctx.screen_loader.get_area(screen_name, area_name).pc_rect
    x1 = rect.x2 - 145 if area_name.endswith('价值') else rect.x1
    color = (142, 142, 142) if area_name.endswith('价值') else (20, 20, 20)
    cv2.rectangle(screen, (x1, rect.y1), (rect.x2 - 1, rect.y2 - 1), color, -1)
    cv2.putText(screen, text, (x1 + 3, rect.y2 - 9), cv2.FONT_HERSHEY_SIMPLEX,
                0.75, (255, 255, 255), 2, cv2.LINE_AA)


def warehouse_frames(ctx: TestContext) -> list[MatLike]:
    """用录像首尾与一张合成中间帧模拟逐件转存，非实拍逐件过程。"""
    before = ctx.load_screen('贝果-仓库', 'clear_loadout_backpack_carried').copy()
    done = ctx.load_screen('贝果-仓库', 'clear_loadout_prepare_warehouse_empty')
    # 录像鼠标遮住「仓」字；合成鼠标移开后的按钮，不降低产品的识别门槛。
    before[990:1060, 190:445] = done[990:1060, 190:445]
    middle = before.copy()
    middle[172:284, 218:316] = done[172:284, 218:316]
    paint_count(ctx, middle, '贝果-仓库', '背包数量', '1/50')
    paint_count(ctx, middle, '贝果-仓库', '仓库数量', '187/280')
    return [before, middle, done]


def unload_frames(ctx: TestContext) -> list[MatLike]:
    """逐格合成十个卸装结果，模拟实际数值下降与卸背包后的容量变化。"""
    before = ctx.load_screen('贝果-备战', 'clear_loadout_carried').copy()
    empty = ctx.load_screen('贝果-备战', 'clear_loadout_empty')
    paint_count(ctx, before, '贝果-备战', '背包数量', '0/50')
    frames = [before]
    values = {'武备价值': 270000, '装备价值': 160000, '道具价值': 78000}
    decrements = [90000, 90000, 90000, 80000, 70000, 10000, 45000, 15000, 15000, 3000]
    index = 0
    for group, centers in LOADOUT_GROUPS:
        for center in centers:
            current = frames[-1].copy()
            x, y = center.tuple()
            current[y-45:y+45, x-45:x+45] = empty[y-45:y+45, x-45:x+45]
            values[group] -= decrements[index]
            paint_count(ctx, current, '贝果-备战', group, str(values[group]))
            if index == 5:
                paint_count(ctx, current, '贝果-备战', '背包数量', '0/20')
            frames.append(current)
            index += 1
    return frames


def detail_frame(ctx: TestContext, screen: MatLike, source: Point) -> MatLike:
    """以录像详情面板合成已装备槽的菜单，不作为连续实机证据。"""
    result = screen.copy()
    if source.x == 1360:
        detail = ctx.load_screen('贝果-备战', 'clear_loadout_weapon_detail')
        result[140:918, 1440:1845] = detail[140:918, 1440:1845]
        return result
    state = 'clear_loadout_equipment_detail' if source.y < 400 else 'clear_loadout_item_detail'
    detail = ctx.load_screen('贝果-备战', state)
    result[175:875, 1040:1445] = detail[175:875, 1040:1445]
    return result


@contextmanager
def running_operation(op: Operation) -> Iterator[None]:
    """为一次测试开启运行态，断言失败时也清理运行态和事件监听。"""
    enter_running_state(op.ctx)
    try:
        yield
    finally:
        reset_running_state(op.ctx, op)


def mock_loadout_ocr(
    ctx: TestContext, monkeypatch: pytest.MonkeyPatch, area_name: str,
    full_texts: list[str], crop_texts: list[str] | None,
) -> MagicMock:
    """按区域提供备战 OCR 数据；仅指定价值区异常，其余四项为零携带。"""
    panel: list[OcrMatchResult] = []
    responses: dict[tuple[Rect, bool], list[OcrMatchResult]] = {}
    for name, label in (('武备价值', '代理人武备'), ('装备价值', '装备'), ('道具价值', '道具')):
        rect = ctx.screen_loader.get_area('贝果-备战', name).pc_rect
        texts = full_texts if name == area_name else [label, '0']
        matches = [OcrMatchResult(1, rect.x1 + i * 40, rect.y1 + 5, 30, 20, data=text)
                   for i, text in enumerate(texts)]
        panel.extend(matches)
        if name == area_name:
            responses[rect, False] = matches
            if crop_texts is not None:
                responses[rect, True] = [OcrMatchResult(1, 0, 0, 10, 10, data=text) for text in crop_texts]
    responses[Rect(1000, 0, 1920, 1080), True] = panel
    for name, value in (('背包数量', '0/20'), ('安全箱数量', '0/5')):
        rect = ctx.screen_loader.get_area('贝果-备战', name).pc_rect
        responses[rect, True] = [OcrMatchResult(1, 0, 0, 10, 10, data=value)]

    def recognize(screen: MatLike, *, rect: Rect, crop_first: bool, color_range: object = None) -> list[OcrMatchResult]:
        return responses[rect, crop_first]

    ocr = MagicMock(side_effect=recognize)
    monkeypatch.setattr(ctx.ocr_service, 'get_ocr_result_list', ocr)
    return ocr
