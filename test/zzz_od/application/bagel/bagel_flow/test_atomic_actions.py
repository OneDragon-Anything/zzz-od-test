"""独立动作、旧格式迁移与真实截图边界回归。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from zzz_od.application.bagel.bagel_close_search import BagelCloseSearch
from zzz_od.application.bagel.bagel_flow import (
    BagelFlow,
    BagelStep,
    load_published_flow,
    read_flow,
)
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_route import BagelRoute
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow
from zzz_od.application.bagel.bagel_store import BagelStoreSafe
from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe

pytestmark = pytest.mark.usefixtures('no_round_wait')


def legacy_data() -> dict:
    """构造含用户坐标和参数的版本一流程，不依赖发布资源版本。"""
    route = BagelRoute.from_dict('janus_high_a', yaml.safe_load((Path(__file__).parent / 'data/v1_waypoints.yml').read_text(encoding='utf-8')))
    steps = [BagelStep('spawn', 'spawn', '出生')]
    for target, action in (('box', 'open_box'), ('safe', 'unlock_safe')):
        steps.extend(
            (
                BagelStep(
                    f'move_{target}', 'move', '旧移动', target, route.points_for(target)
                ),
                BagelStep(f'open_{target}', action, '旧交互'),
                BagelStep(f'store_{target}', 'store', '旧收集', target),
            )
        )
    steps.append(BagelStep('exit', 'exit', '退出'))
    data = BagelFlow('custom', '用户流程', route.map_id, tuple(steps)).to_dict()
    data['version'] = 1
    data['steps'][4]['waypoints'][1]['xy'] = [200, 108]
    data['steps'][4]['waypoints'][1]['tolerance'] = 1.4
    data['steps'][4]['navigation'] = {
        'timeout': 110,
        'brake_distance': 4,
        'interaction_distance': 7,
    }
    return data


def test_legacy_migration_preserves_user_file_and_parameters(tmp_path: Path) -> None:
    """旧草稿拆分稳定，不改文件；每步保留坐标、容差与导航覆盖项。"""
    path = tmp_path / 'legacy.yml'
    path.write_text(yaml.safe_dump(legacy_data(), allow_unicode=True), encoding='utf-8')
    before = path.read_bytes()
    flow = read_flow(path)
    assert flow == read_flow(path)
    assert path.read_bytes() == before
    assert len(flow.steps) == 15 and flow.to_dict()['version'] == 4
    safe_moves = list(flow.steps[6:9])
    assert all(s.action == 'move' and s.target is None for s in safe_moves)
    assert len(safe_moves) == 3
    assert safe_moves[1].waypoints[0].xy == (200, 108)
    assert safe_moves[1].waypoints[0].tolerance == 1.4
    assert all(s.navigation.timeout == 110 for s in safe_moves)
    approach = next(
        s for s in flow.steps if s.action == 'approach' and s.target == 'safe'
    )
    assert approach.navigation.effective_interaction_distance == 7
    assert safe_moves[-1].navigation.effective_brake_distance == 4


@pytest.mark.parametrize('mutation', ['unknown', 'stop', 'duplicate', 'order'])
def test_legacy_corruption_rejected_before_migration(mutation: str) -> None:
    """迁移不能掩盖旧文件损坏。"""
    data = legacy_data()
    if mutation == 'unknown':
        data['steps'][4]['surprise'] = True
    elif mutation == 'stop':
        data['steps'][4]['waypoints'][-2]['stop'] = False
    elif mutation == 'duplicate':
        data['steps'][4]['id'] = data['steps'][1]['id']
    else:
        data['steps'][2], data['steps'][3] = data['steps'][3], data['steps'][2]
    with pytest.raises(ValueError):
        BagelFlow.from_dict(data)


@pytest.mark.parametrize(
    'removed_action', ['approach', 'interact', 'unlock', 'store', 'close']
)
def test_complete_flow_requires_each_action(removed_action: str) -> None:
    """完整正式流程不能靠隐藏操作补齐交互、解锁、收集或关闭。"""
    flow = load_published_flow('janus_high_a')
    broken = replace(
        flow, steps=tuple(s for s in flow.steps if s.action != removed_action)
    )
    with pytest.raises(ValueError):
        BagelFlow.from_dict(broken.to_dict())


def test_move_cannot_hide_multiple_points() -> None:
    """一个移动步骤只有一个目的地，不能重新变成整个导航链。"""
    data = load_published_flow('janus_high_a').to_dict()
    data['steps'][1]['waypoints'].append(data['steps'][2]['waypoints'][-1])
    with pytest.raises(ValueError, match='一个位置'):
        BagelFlow.from_dict(data)


def test_coordinate_move_ignores_prompt_and_finishes_at_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """途中同类交互提示不结束坐标移动，到路点后无需提示即可完成。"""
    flow = load_published_flow('janus_high_a')
    step = flow.steps[1]
    op = BagelRunFlow(MagicMock(), flow).build_operation(step)
    assert isinstance(op, BagelNavigate) and op.coordinate_only
    op.last_screenshot_time = 1
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(op, 'round_by_find_area', lambda *_: op.round_success())
    monkeypatch.setattr(op, 'minimap', lambda: None)
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    monkeypatch.setattr(op.vision, 'locate', lambda _: (90, 100))
    monkeypatch.setattr(op, '_cruise_toward', lambda *_: op.round_wait('继续移动'))
    assert op.move_to_target().status == '继续移动'
    monkeypatch.setattr(op.vision, 'locate', lambda _: step.waypoints[0].xy)
    monkeypatch.setattr(
        op,
        'round_by_find_area',
        lambda _, __, area: op.round_success() if area == '按键-普通攻击' else op.round_fail(),
    )
    assert op.move_to_target().status == BagelNavigate.STATUS_WAYPOINT
    op.ctx.controller.interact.assert_not_called()


def test_approach_starts_at_final_target_and_braking_remains_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """靠近只含唯一目的地；提前松键仍发生在独立接近点步骤。"""
    flow = load_published_flow('janus_high_a')
    runner = BagelRunFlow(MagicMock(), flow)
    approach = runner.build_operation(flow.steps[9])
    approach.handle_init()
    assert approach.waypoint_index == 0 and approach.final_approach
    assert not approach.coordinate_only
    move = runner.build_operation(flow.steps[8])
    move.last_screenshot_time = 1
    monkeypatch.setattr(move, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(move, 'round_by_find_area', lambda *_: move.round_success())
    monkeypatch.setattr(move, 'minimap', lambda: None)
    monkeypatch.setattr(move.vision, 'player_angle', lambda _: 0)
    target = flow.steps[8].waypoints[0].xy
    monkeypatch.setattr(move.vision, 'locate', lambda _: (target[0] - 5, target[1]))
    assert move.move_to_target().result == OperationRoundResultEnum.WAIT
    move.ctx.controller.move_w.assert_not_called()


def record_controller(test_context: object, monkeypatch: pytest.MonkeyPatch) -> object:
    """保留截图存档读取，只记录可能发送的游戏输入。"""
    controller = test_context.controller
    for name in ('interact', 'click', 'drag_to'):
        monkeypatch.setattr(controller, name, MagicMock())
    return controller


@pytest.mark.parametrize('phase', ['interact', 'unlock'])
def test_safe_phase_at_real_unlock_screen(
    test_context: object, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    """同一光圈截图：交互阶段结束，解锁阶段才准备光圈点按。"""
    controller = record_controller(test_context, monkeypatch)
    test_context.mock_screen('贝果-局内', '电子保险箱第1轮小圈')
    op = BagelUnlockSafe(test_context, phase=phase)
    op.screenshot()
    result = op.enter_unlock()
    assert result.is_success
    assert result.status == (op.STATUS_READY if phase == 'interact' else '已在解锁界面')
    assert op.hits_done == 0
    controller.interact.assert_not_called()


def test_unlock_does_not_perform_initial_interaction(
    test_context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """仍站在保险箱前时，只选解锁应报前置不符，不能代按 F。"""
    controller = record_controller(test_context, monkeypatch)
    test_context.mock_screen('贝果-局内', '电子保险箱F提示')
    op = BagelUnlockSafe(test_context, phase='unlock')
    op.screenshot()
    assert op.enter_unlock().is_fail
    controller.interact.assert_not_called()


def test_store_stops_if_panel_is_interrupted(
    test_context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """收集中被攻击关闭面板后停止，不补做交互。"""
    controller = record_controller(test_context, monkeypatch)
    op = BagelStoreSafe(test_context)
    test_context.mock_screen('贝果-局内', '雅努斯箱前-r07-32s')
    op.screenshot()
    assert op.store_next().result == OperationRoundResultEnum.WAIT
    result = op.store_next()
    assert result.is_fail
    assert result.status == '搜查面板已关闭，请重新执行交互步骤'
    controller.interact.assert_not_called()
    controller.click.assert_not_called()
    controller.drag_to.assert_not_called()


def test_close_waits_for_search_without_collecting(
    test_context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """关闭动作等待搜索结束，不发送拖拽、交互或全部拾取。"""
    controller = record_controller(test_context, monkeypatch)
    op = BagelCloseSearch(test_context)
    test_context.mock_screen('贝果-局内', '武备箱搜查中-r07')
    op.screenshot()
    assert op.close_panel().status == '等待搜查完成再关闭'
    controller.click.assert_not_called()
    controller.drag_to.assert_not_called()
    controller.interact.assert_not_called()
