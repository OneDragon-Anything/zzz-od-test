"""HollowRunner.try_move_by_map 寻路回归测试。

修复背景: 空洞寻路中「目标格已被踩到脚下」时 next_to_move 为 None,
旧代码在日志打印时直接访问 next_to_move.entry 触发 AttributeError 崩溃。
修复后 None 检查提前, 走 round_retry('自动寻路失败') 重试路径。

覆盖:
- get_next_to_move 返回 None(没有目标): try_move_by_map 直接返回 None
- target.next_node_to_move 为 None(目标格在脚下/空白格): 不崩, 返回「自动寻路失败」重试
- next_to_move 正常时: 走移动分支, 恰好发出一次点击移动命令
- path_step_cnt == 999 兜底标识时: 不发出移动命令, 走重试
"""
from typing import Optional

import numpy as np

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroEntry
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import (
    HollowZeroMap,
    HollowZeroMapNode,
)
from zzz_od.hollow_zero.hollow_runner import HollowRunner


def _make_map_with_target(
    target_entry: HollowZeroEntry,
) -> tuple[HollowZeroMap, HollowZeroMapNode]:
    """构造当前格 + 一步可达目标格的地图, 返回 (map, 目标节点)。

    目标格 need_step=0 时(空白格/当前格), 寻路算不出「第一步要点的节点」,
    next_node_to_move 为 None —— 复现修复前崩溃的场景。
    """
    cur = HollowZeroMapNode(
        Rect(0, 0, 50, 50), HollowZeroEntry('9000-当前', need_step=0)
    )
    target = HollowZeroMapNode(Rect(60, 0, 110, 50), target_entry)
    hollow_map = HollowZeroMap([cur, target], 0, {0: [1], 1: [0]})

    # 必须先寻路 才会设置 path_step_cnt / path_first_need_step_node 等路径信息
    from zzz_od.hollow_zero.hollow_map import hollow_pathfinding
    hollow_pathfinding.search_map(hollow_map, set(), [])

    return hollow_map, target


def _make_screen() -> np.ndarray:
    """构造一张可正常走 OCR 流程的测试图(1080p 纯白)。

    正常移动分支会调用 check_info_before_move -> OCR 识别层级文本,
    图太小(如 64x64)会让 OCR 内部 resize 报错, 因此用接近真实画面尺寸的图。
    """
    return np.full((1080, 1920, 3), 255, dtype=np.uint8)


class TestTryMoveByMap:

    def _install_click_spy(self, test_context) -> list[Point]:
        """包装 controller.click 记录移动点击, 返回记录列表。"""
        clicked: list[Point] = []
        orig_click = test_context.controller.click

        def spy_click(pos: Point = None, press_time: float = 0,
                      pc_alt: bool = False, gamepad_key: Optional[str] = None) -> bool:
            clicked.append(pos)
            return orig_click(pos, press_time, pc_alt, gamepad_key)

        test_context.controller.click = spy_click
        return clicked

    def test_get_next_to_move_none_returns_none(self, test_context) -> None:
        """get_next_to_move 返回 None(本轮没有目标) -> try_move_by_map 直接返回 None。"""
        hollow_map, target = _make_map_with_target(
            HollowZeroEntry('0001-邦布商人', need_step=1)
        )
        test_context.withered_domain.get_next_to_move = lambda cm: None
        runner = HollowRunner(test_context)
        result = runner.try_move_by_map(_make_screen(), 0.0, hollow_map)

        assert result is None

    def test_next_to_move_none_returns_retry(self, test_context) -> None:
        """target.next_node_to_move 为 None(目标格在脚下/空白格) -> 返回「自动寻路失败」重试, 不崩溃。"""
        hollow_map, target = _make_map_with_target(
            HollowZeroEntry('9001-空白未通行', is_benefit=False, need_step=0)
        )
        assert target.next_node_to_move is None  # 前置条件: 复现 None 场景

        test_context.withered_domain.get_next_to_move = lambda cm: target
        runner = HollowRunner(test_context)
        result = runner.try_move_by_map(_make_screen(), 0.0, hollow_map)

        assert result is not None
        assert result.status == '自动寻路失败'

    def test_normal_target_moves_once(self, test_context) -> None:
        """next_to_move 正常(need_step=1 事件格) -> 走移动分支, 恰好发出一次点击命令。"""
        hollow_map, target = _make_map_with_target(
            HollowZeroEntry('0001-邦布商人', need_step=1)
        )
        assert target.next_node_to_move is not None  # 前置条件

        # 正常移动分支会更新地图当前格类型(空白已通行) 需要数据服务已加载词条
        test_context.withered_domain.data_service.reload()
        test_context.withered_domain.get_next_to_move = lambda cm: target
        # 额外任务完成判定与本测试无关 固定为未完成 确保走到移动分支
        runner = HollowRunner(test_context)
        runner._check_extra_task_finished = lambda screen, cm: False
        clicked = self._install_click_spy(test_context)
        result = runner.try_move_by_map(_make_screen(), 0.0, hollow_map)

        assert result is not None
        assert len(clicked) == 1  # 恰好点击了一次目标格
        assert clicked[0] is not None

    def test_999_fallback_does_not_move(self, test_context) -> None:
        """path_step_cnt == 999(兜底标识) -> 不发移动命令, 走重试路径。"""
        hollow_map, target = _make_map_with_target(
            HollowZeroEntry('0001-邦布商人', need_step=1)
        )
        target.next_node_to_move.path_step_cnt = 999  # 标记兜底

        test_context.withered_domain.get_next_to_move = lambda cm: target
        clicked = self._install_click_spy(test_context)
        runner = HollowRunner(test_context)
        result = runner.try_move_by_map(_make_screen(), 0.0, hollow_map)

        # 999 兜底属于「寻路未成功」, 不移动 直接走重试(间隔 1 秒限制)
        assert result.status == '自动寻路失败'
        assert len(clicked) == 0
