"""冻结历史标注，比较原多参考图、多参考图缓存与固定地图缓存。"""

from __future__ import annotations

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
import yaml

from zzz_od.application.bagel.bagel_fixed_map import _load_snapshot
from zzz_od.application.bagel.bagel_map_locator import minimap_mask
from zzz_od.application.bagel.bagel_minimap import (
    extract_features,
    match_features,
    register_minimap,
)
from zzz_od.application.bagel.bagel_route import resource_root
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision

DATA: Path = Path(__file__).parent / 'data'
SCREENS: Path = Path(__file__).resolve().parents[5] / 'screens/贝果-局内'


class LegacyVision:
    """仅用于对照的冻结旧算法，正式代码不保留回退分支。"""

    def __init__(self, map_id: str, cached: bool) -> None:
        """旧参数取测试夹具，原参考图仍取主仓保留素材。"""
        self.cached: bool = cached
        self.data: dict = yaml.safe_load((DATA / f'{map_id}_legacy.yml').read_text(encoding='utf-8'))
        self.references: list[list[tuple]] = [[], []]
        for reference in self.data['references']:
            image = cv2.imdecode(np.fromfile(resource_root(map_id) / reference['image'], np.uint8), cv2.IMREAD_COLOR)
            mask = minimap_mask(image, self.data['mask'])
            matrix = np.asarray(reference['to_global'])
            for mode in (0, 1):
                preprocessed = self.prepare(image, mode)
                self.references[mode].append((
                    extract_features(preprocessed, mask) if cached else preprocessed,
                    mask, matrix,
                ))

    def prepare(self, image: np.ndarray, mode: int) -> np.ndarray:
        """保持旧灰度优先、最小颜色通道兜底的顺序。"""
        gray = np.min(image, axis=2) if mode else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        size = self.data['registration_blur_size']
        blurred = cv2.GaussianBlur(gray, (size, size), 0)
        return cv2.createCLAHE(2.0, (8, 8)).apply(blurred)

    def locate(self, crop: np.ndarray) -> tuple[float, float] | None:
        """按旧规则拒绝任何相差超过五像素的参考图结果。"""
        mask = minimap_mask(crop, self.data['mask'])
        anchor = tuple(self.data['anchor_xy'])
        for mode, references in enumerate(self.references):
            current = self.prepare(crop, mode)
            features = extract_features(current, mask) if self.cached else None
            candidates = []
            for image, ref_mask, matrix in references:
                match = match_features(features, image, anchor) if self.cached else register_minimap(current, mask, image, ref_mask, anchor)
                if match is not None:
                    position = matrix[:, :2] @ match.player_position + matrix[:, 2]
                    candidates.append((match.inliers, tuple(float(v) for v in position)))
            if not candidates:
                continue
            for index, (_, first) in enumerate(candidates):
                for _, second in candidates[index + 1:]:
                    if hypot(first[0] - second[0], first[1] - second[1]) > 5:
                        return None
            return max(candidates, key=lambda item: item[0])[1]
        return None


def correct(case: dict, position: tuple[float, float] | None) -> bool:
    """沿用历史逐轴误差容限，拒绝样本必须没有输出坐标。"""
    expected = case['expected']
    return position is None if expected is None else position is not None and bool(np.allclose(position, expected, atol=case['tolerance'], rtol=0))


def main() -> None:
    """轮次与线程固定，全部成功及失败帧均计入统计。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=5)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error('轮次必须为正数')
    cv2.setNumThreads(1)
    cv2.setRNGSeed(18)
    cases = json.loads((DATA / 'historical_cases.json').read_text(encoding='utf-8'))
    crops = []
    for case in cases:
        if case['image'] == '__blank__':
            crop = np.zeros((201, 201, 3), np.uint8)
        else:
            payload = (SCREENS / case['image']).read_bytes()
            case['image_sha256'] = hashlib.sha256(payload).hexdigest()
            crop = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)[206:407, 1533:1734]
        crops.append(crop)
    factories = {
        'legacy': lambda map_id: LegacyVision(map_id, False),
        'cached_references': lambda map_id: LegacyVision(map_id, True),
        'fixed_map': BagelRouteVision,
    }
    engines, cold = {}, {}
    for name, factory in factories.items():
        engines[name], cold[name] = {}, {}
        for map_id in ('janus_high_a', 'janus_high_b'):
            _load_snapshot.cache_clear()
            started = perf_counter()
            engine = factory(map_id)
            load_ms = (perf_counter() - started) * 1000
            index = next(i for i, case in enumerate(cases) if case['map_id'] == map_id)
            started = perf_counter()
            engine.locate(crops[index])
            cold[name][map_id] = {'load_ms': load_ms, 'first_locate_ms': (perf_counter() - started) * 1000}
            engines[name][map_id] = engine
    runs = {name: [[] for _ in cases] for name in factories}
    outputs = {name: [] for name in factories}
    for round_index in range(args.rounds):
        for name in np.random.default_rng(round_index).permutation(list(factories)):
            for index, (case, crop) in enumerate(zip(cases, crops, strict=True)):
                engine = engines[name][case['map_id']]
                started = perf_counter()
                position = engine.locate(crop)
                runs[name][index].append((perf_counter() - started) * 1000)
                if round_index == 0:
                    outputs[name].append(position)
                elif position != outputs[name][index]:
                    raise AssertionError('同一帧的定位结果在重复执行中变化')
        print(f'完成 {round_index + 1}/{args.rounds} 轮', flush=True)
    summary = {}
    for name in factories:
        times = [ms for row in runs[name] for ms in row]
        success = [correct(case, xy) for case, xy in zip(cases, outputs[name], strict=True)]
        summary[name] = {
            'correct': sum(success), 'cases': len(cases), 'measurements': len(times),
            'median_ms': float(np.median(times)), 'p95_ms': float(np.percentile(times, 95)),
            'false_positions': sum(not ok and xy is not None for ok, xy in zip(success, outputs[name], strict=True)),
            'missed_positions': sum(case['expected'] is not None and xy is None for case, xy in zip(cases, outputs[name], strict=True)),
        }
        for label in ('A', 'B'):
            selected = [ms for case, row in zip(cases, runs[name], strict=True) if case['label'] == label for ms in row]
            summary[name][label] = {'median_ms': float(np.median(selected)), 'p95_ms': float(np.percentile(selected, 95))}
    rows = [dict(case, outcomes={name: {'position': outputs[name][index], 'correct': correct(case, outputs[name][index]), 'times_ms': runs[name][index]} for name in factories}) for index, case in enumerate(cases)]
    report = {'opencv': cv2.__version__, 'numpy': np.__version__, 'threads': 1, 'rounds': args.rounds, 'cold': cold, 'summary': summary, 'cases': rows,
              'limitations': '历史标注沿用既有容差，含不同录制批次；并非新增独立人工精密真值，也未做实机验收。'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
