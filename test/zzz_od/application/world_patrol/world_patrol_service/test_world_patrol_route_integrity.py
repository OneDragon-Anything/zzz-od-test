"""shipped world_patrol 路由完整性测试。

``world_patrol_service.get_world_patrol_routes_by_area`` 加载每个路由 yml 时套了
``try/except`` 静默吞异常(``world_patrol_service.py:263-270``),坏路由出包没人知道,
直到用户报「路线没跑」。本测试**直接解析每个路由 yml(不吞异常)**,并校验:

1. ``WorldPatrolRoute.from_dict`` 能解析(键缺失 / 格式错 → 抛错暴露,而非静默跳过);
2. ``op_list`` 每条 ``op_type`` 在 ``WorldPatrolOpType`` 枚举内(``WorldPatrolOperation.from_dict``
   不校验,瞎串也存,运行时才崩);
3. ``tp_name`` 在该区域 ``icon.yml`` 的 ``icon_name`` 集合里 —— 运行时 ``TransportBy3dMap``
   靠它定位传送点,找不到 → ``round_fail('未找到目标传送点配置')``(``transport_by_3d_map.py:181``)。

SR 原版的路由完整性模式(data arity / item 枚举)在 ZZZ 不适用:``WorldPatrolOpType`` 只有
``move``、``data`` 恒为坐标。这里只挑 ZZZ 真实静默风险。
"""

import glob
import os

import yaml
from test.conftest import TestContext

from zzz_od.application.world_patrol.world_patrol_area import icon_yaml_path
from zzz_od.application.world_patrol.world_patrol_route import (
    WorldPatrolOpType,
    WorldPatrolRoute,
)
from zzz_od.application.world_patrol.world_patrol_service import area_route_dir


def _area_icon_names(area) -> set[str]:
    """读区域的 icon.yml,返回 icon_name 集合(不依赖 large_map_list / road_mask 加载)。"""
    path = icon_yaml_path(area)
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        return set()
    return {i.get('icon_name', '') for i in data if isinstance(i, dict)}


def test_world_patrol_route_integrity(test_context: TestContext) -> None:
    """所有 shipped 路由:可解析 + op_type 合法 + tp_name 能对应到区域图标。"""
    service = test_context.world_patrol_service
    if not service.area_list:
        service.load_area()
    assert service.area_list, 'area_list 为空(map_area_all.yml 没加载?目录结构变了?)'

    valid_op_types = {t.value for t in WorldPatrolOpType}
    parse_errors: list[str] = []
    bad_ops: list[str] = []
    missing_tp: list[str] = []
    checked = 0

    for area in service.area_list:
        route_dir = area_route_dir(area)
        if not os.path.exists(route_dir):
            continue
        icon_names = _area_icon_names(area)
        for yml_path in sorted(glob.glob(os.path.join(route_dir, '*.yml'))):
            checked += 1
            with open(yml_path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
            try:
                route = WorldPatrolRoute.from_dict(data, area)
            except Exception as e:  # noqa: BLE001 把被服务层吞掉的解析错顶出来
                parse_errors.append(f'{yml_path}: {e}')
                continue
            for op in route.op_list:
                if op.op_type not in valid_op_types:
                    bad_ops.append(f'{yml_path}: op_type={op.op_type!r} 不在 {valid_op_types}')
            if route.tp_name not in icon_names:
                missing_tp.append(
                    f'{yml_path}: tp_name={route.tp_name!r} 不在 {area.full_id} 的 icon.yml({sorted(icon_names)})'
                )

    assert checked > 0, '未检查到任何路由 yml(world_patrol 路由目录结构变了?)'
    assert not parse_errors, f'路由解析失败(服务层静默吞了): {parse_errors}'
    assert not bad_ops, f'非法 op_type: {bad_ops}'
    assert not missing_tp, f'tp_name 找不到对应图标(运行时会 round_fail): {missing_tp}'
