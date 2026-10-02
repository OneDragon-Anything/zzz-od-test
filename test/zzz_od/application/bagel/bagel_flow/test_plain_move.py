"""普通移动无需容器，旧路线的实际参数仍能保留。"""

from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from zzz_od.application.bagel.bagel_flow import (
    BagelFlow,
    load_published_flow,
    read_flow,
)
from zzz_od.application.bagel.bagel_route import BagelRoute
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow


def plain_flow(map_id: str = 'janus_high_a') -> dict:
    """不包含任何箱子步骤的独立移动流程。"""
    return {
        'version': 4, 'id': map_id, 'name': '单纯移动', 'map_id': map_id,
        'steps': [
            {'id': 'spawn', 'action': 'spawn', 'name': '检查出生'},
            {'id': 'walk', 'action': 'move', 'name': '走到空地',
             'waypoints': [{'name': '空地', 'xy': [115, 100]}], 'navigation': {'final_mode': 'coordinate'}},
            {'id': 'exit', 'action': 'exit', 'name': '退出'},
        ],
    }


@pytest.mark.parametrize('map_id', ['janus_high_a', 'janus_high_b'])
def test_move_without_any_container_roundtrips_and_executes(
    map_id: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无需前后箱子推断，真实执行器按坐标到达，不识别容器提示。"""
    flow = BagelFlow.from_dict(plain_flow(map_id))
    assert flow.to_dict() == plain_flow(map_id)
    step = flow.steps[1]
    assert step.target is None
    assert step.waypoints[0].arrival_radius == step.waypoints[0].passed_radius == 2
    op = BagelRunFlow(MagicMock(), flow).build_operation(step)
    assert op.destination == 'move' and op.timeout_seconds == 45
    op.last_screenshot_time = 1
    monkeypatch.setattr(op, 'is_bagel_result', lambda: False)
    checks = MagicMock(return_value=op.round_success())
    monkeypatch.setattr(op, 'round_by_find_area', checks)
    monkeypatch.setattr(op, 'minimap', lambda: None)
    monkeypatch.setattr(op.vision, 'locate', lambda _: (115, 100))
    monkeypatch.setattr(op.vision, 'player_angle', lambda _: 0)
    assert op.move_to_target().status == op.STATUS_WAYPOINT
    assert [call.args[-1] for call in checks.call_args_list] == ['按键-普通攻击']
    op.ctx.controller.interact.assert_not_called()
    op.ctx.controller.move_w.assert_not_called()


@pytest.mark.parametrize('field,value', [
    ('target', 'safe'), ('target', None), ('stage', 'box'), ('role', 'entry'),
    ('final_mode', 'short_steps'), ('interaction_distance', 10),
    ('passed_tolerance', float('nan')),
])
def test_plain_move_rejects_container_fields(field: str, value: object) -> None:
    """新版不把容器字段悄悄藏在普通移动中。"""
    data = plain_flow()
    step = data['steps'][1]
    if field == 'target':
        step[field] = value
    elif field in ('final_mode', 'interaction_distance'):
        step['navigation'][field] = value
    else:
        step['waypoints'][0][field] = value
    with pytest.raises(ValueError):
        BagelFlow.from_dict(data)


def test_version_two_migration_keeps_coordinates_and_effective_parameters(tmp_path: Path) -> None:
    """旧目标的有效半径、时限和可生效松键设置转为明确参数，原文件保持原样。"""
    raw = dict(plain_flow(), version=2)
    # 固定版本二原始结构，不能只把新版文件的版本号改成二。
    moves = [
        {'id': f'move_{i}', 'action': 'move', 'name': role, 'target': target,
         'waypoints': [{'name': role, 'xy': xy, 'stage': target, 'role': role}],
         'navigation': {}}
        for i, (target, role, xy) in enumerate((
            ('box', 'turn', [110, 100]), ('safe', 'entry', [186.6, 84.9]),
            ('safe', 'turn', [201.6, 109.5]), ('safe', 'approach', [213, 110]),
        ))
    ]
    raw['steps'] = [raw['steps'][0], *moves, raw['steps'][-1]]
    moves[-1]['navigation']['brake_distance'] = 4
    path = tmp_path / 'old.yml'
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding='utf-8')
    before = path.read_bytes()
    migrated = read_flow(path)
    for old, step in zip(moves, (s for s in migrated.steps if s.action == 'move'), strict=True):
        point = BagelRoute.from_dict('janus_high_a', {'map_id': 'janus_high_a', 'waypoints': old['waypoints']}, complete=False, check_roles=False).waypoints[0]
        assert step.target is None
        assert step.waypoints[0].xy == point.xy
        assert step.waypoints[0].arrival_radius == point.arrival_radius
        assert step.waypoints[0].passed_radius == point.passed_radius
        assert step.navigation.timeout == (75 if old['target'] == 'safe' else 45)
        assert not {'target'} & step.to_dict().keys()
        assert not {'stage', 'role', 'stop'} & step.to_dict()['waypoints'][0].keys()
    assert migrated.steps[-2].navigation.brake_distance == 4
    assert path.read_bytes() == before
    assert BagelFlow.from_dict(migrated.to_dict()) == migrated


@pytest.mark.parametrize('mode', ['coordinate', 'small_steps'])
def test_v4_all_movement_requires_exactly_one_destination(mode: str) -> None:
    """普通移动和靠近均拒绝缺点、多点和固定方向模式。"""
    for action in ('move', 'approach'):
        data = plain_flow()
        step = data['steps'][1]
        step['action'] = action
        step['navigation']['final_mode'] = mode
        if action == 'approach':
            step['target'] = 'box'
            step['waypoints'][0].update(stage='box', role='target')
        assert len(BagelFlow.from_dict(data).steps[1].waypoints) == 1
        for points in ([], step['waypoints'] * 2):
            invalid = deepcopy(data)
            invalid['steps'][1]['waypoints'] = points
            with pytest.raises(ValueError):
                BagelFlow.from_dict(invalid)
        step['navigation']['final_mode'] = 'short_steps'
        with pytest.raises(ValueError):
            BagelFlow.from_dict(data)


def test_v3_direction_migrates_to_destination_without_writing_source(tmp_path: Path) -> None:
    """旧两点中的尾点变为唯一目的地，显式参数保留，保存后不再携带方向。"""
    raw = load_published_flow('janus_high_a').to_dict()
    raw['version'] = 3
    for step in raw['steps']:
        if step['action'] == 'move':
            step['navigation'].pop('final_mode', None)
        elif step['action'] == 'approach':
            step['navigation']['final_mode'] = 'coordinate'
    step = raw['steps'][9]
    end = deepcopy(step['waypoints'][0])
    start = dict(end, name='旧方向', xy=[201, 105], role='approach')
    step['waypoints'] = [start, end]
    step['navigation'] = {'final_mode': 'short_steps', 'timeout': 123, 'brake_distance': 4, 'interaction_distance': 8}
    path = tmp_path / 'v3.yml'
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding='utf-8')
    before = path.read_bytes()
    flow = read_flow(path)
    result = flow.steps[9]
    assert path.read_bytes() == before
    assert len(result.waypoints) == 1 and result.waypoints[0].xy == tuple(end['xy'])
    assert (result.id, result.name, result.target) == (step['id'], step['name'], step['target'])
    assert result.navigation.to_dict() == dict(step['navigation'], final_mode='small_steps')
    assert flow.to_dict()['version'] == 4
    assert BagelFlow.from_dict(flow.to_dict()) == flow
