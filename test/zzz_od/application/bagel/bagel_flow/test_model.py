"""流程模型、资源来源、导航覆盖项与原子写入。"""

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from zzz_od.application.bagel.bagel_flow import (
    BagelFlow,
    NavigationOptions,
    draft_path,
    load_published_flow,
    read_flow,
    write_flow,
)
from zzz_od.application.bagel.bagel_navigate import BagelNavigate


@pytest.mark.parametrize('map_id,count', [('janus_high_a', 15), ('janus_high_b', 6)])
def test_published_roundtrip(map_id: str, count: int) -> None:
    """两地图正式流程可完整回读。"""
    flow = load_published_flow(map_id)
    assert len(flow.steps) == count
    write_flow(draft_path(map_id), flow)
    assert read_flow(draft_path(map_id)) == flow


@pytest.mark.parametrize(
    'mutation',
    [
        'version',
        'unknown',
        'duplicate',
        'store_first',
        'after_exit',
        'nan',
        'mode',
        'stage',
        'target',
        'extra',
    ],
)
def test_invalid_flow_rejected(mutation: str) -> None:
    """拒绝坏结构和会错误执行的顺序。"""
    data = load_published_flow('janus_high_a').to_dict()
    if mutation == 'version':
        data['version'] = True
    elif mutation == 'unknown':
        data['steps'][2]['action'] = 'press_key'
    elif mutation == 'duplicate':
        data['steps'][2]['id'] = data['steps'][1]['id']
    elif mutation == 'store_first':
        data['steps'][2], data['steps'][3] = data['steps'][3], data['steps'][2]
    elif mutation == 'after_exit':
        data['steps'].insert(1, data['steps'].pop())
    elif mutation == 'nan':
        data['steps'][1]['waypoints'][0]['tolerance'] = float('nan')
    elif mutation == 'mode':
        data['steps'][1]['navigation']['final_mode'] = 'teleport'
    elif mutation == 'stage':
        data['steps'][1]['waypoints'][0]['stage'] = 'safe'
    elif mutation == 'target':
        data['steps'][1]['target'] = 'unknown'
    else:
        data['steps'][3]['navigation'] = {'timeout': 10}
    with pytest.raises(ValueError):
        BagelFlow.from_dict(data)


def test_reorder_containers_and_remove_safe() -> None:
    """完整容器链可重排或删除，不再固定先武备箱后保险箱。"""
    flow = load_published_flow('janus_high_a')
    swapped = replace(
        flow, steps=(flow.steps[0], *flow.steps[6:14], *flow.steps[1:6], flow.steps[-1])
    )
    assert BagelFlow.from_dict(swapped.to_dict()) == swapped
    short = replace(flow, steps=(*flow.steps[:6], flow.steps[-1]))
    assert BagelFlow.from_dict(short.to_dict()) == short


def test_published_route_and_explicit_snapshot_used() -> None:
    """默认导航读取正式流程，显式传入的快照保留自定义参数。"""
    flow = load_published_flow('janus_high_a')
    step = flow.steps[1]
    step = replace(
        step,
        name='只是改名',
        waypoints=(replace(step.waypoints[0], xy=(111, 102)), *step.waypoints[1:]),
        navigation=NavigationOptions(timeout=130, brake_distance=4),
    )
    ctx = MagicMock(current_instance_idx=99)
    nav = BagelNavigate(
        ctx,
        destination='move',
        coordinate_only=True,
        route_data=step.route(flow.map_id),
        navigation=step.navigation,
        require_spawn=False,
    )
    assert nav.active_waypoints[0][1] == (111, 102)
    assert nav.timeout_seconds == 130
    assert nav.navigation.effective_brake_distance == 4
    assert (
        BagelNavigate(ctx).active_waypoints[0][1]
        == flow.steps[1].waypoints[0].xy
    )


def test_atomic_write_failure_preserves_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """替换失败后旧草稿可加载，临时文件清理。"""
    flow = load_published_flow('janus_high_b')
    path = draft_path(flow.map_id)
    write_flow(path, flow)
    before = path.read_bytes()
    monkeypatch.setattr(Path, 'replace', MagicMock(side_effect=OSError('模拟失败')))
    with pytest.raises(OSError):
        write_flow(path, replace(flow, name='新名称'))
    assert path.read_bytes() == before
    assert not list(path.parent.glob('*.tmp'))


def test_corrupt_resource_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """坏正式资源必须报错。"""
    monkeypatch.setattr(
        'zzz_od.application.bagel.bagel_flow.resource_root', lambda _: tmp_path
    )
    (tmp_path / 'flow.yml').write_text(
        yaml.safe_dump({'version': 99}), encoding='utf-8'
    )
    with pytest.raises(ValueError):
        load_published_flow('janus_high_a')


def test_repeated_container_prompt_requires_target_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """另一处同类容器提示须先停稳核对位置，不能继续移动或提前到达。"""
    flow = load_published_flow('janus_high_b')
    step = flow.steps[1]
    nav = BagelNavigate(
        MagicMock(),
        map_id=flow.map_id,
        route_data=step.route(flow.map_id),
        check_target_position=True,
        require_spawn=False,
    )
    nav.last_screenshot_time = 1
    monkeypatch.setattr(nav, 'is_bagel_result', lambda: False)
    monkeypatch.setattr(nav, 'round_by_find_area', lambda *args: (
        nav.round_success() if args[-1] in ('按键-普通攻击', '武备箱交互', '交互F键')
        else nav.round_fail()
    ))
    monkeypatch.setattr(nav, 'minimap', lambda: None)
    monkeypatch.setattr(nav.vision, 'player_angle', lambda _: 0)
    monkeypatch.setattr(nav.vision, 'locate', lambda _: (100, 100))
    cruise = MagicMock(return_value=nav.round_wait('继续移动'))
    monkeypatch.setattr(nav, '_cruise_toward', cruise)
    assert nav.move_to_target().status == '发现容器提示，松键后确认停稳'
    nav.last_screenshot_time = nav._settle_until
    assert nav.move_to_target().status == '容器交互提示与当前目标位置不符'
    cruise.assert_not_called()
    nav.handle_init()
    monkeypatch.setattr(nav.vision, 'locate', lambda _: step.waypoints[-1].xy)
    assert nav.move_to_target().status == '发现容器提示，松键后确认停稳'
    nav.last_screenshot_time = nav._settle_until
    assert nav.move_to_target().status == nav.STATUS_ARRIVED_BOX
