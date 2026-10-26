"""首领头像检测回归测试。

验证 boss_avatar 任务：薇斯珀头像命中时写入 首领-薇斯珀，其它首领头像不命中。
流水线用多边形模板 target_state/boss_vesper，避开左侧血条与左下角数值。
"""
import os

from test.conftest import TestContext

from one_dragon.utils import cv2_utils
from zzz_od.auto_battle.target_state.target_state_checker import TargetStateChecker
from zzz_od.game_data.target_state import DETECTION_TASKS

_IMG_DIR = os.path.join(os.path.dirname(__file__), 'test_boss_avatar_state')
_STATE_NAME = '首领-薇斯珀'


def _run_task(ctx: TestContext, file_name: str) -> dict:
    """跑一次 boss_avatar 任务 返回 状态名 -> 识别结果。"""
    checker = TargetStateChecker(ctx)
    task = next(t for t in DETECTION_TASKS if t.task_id == 'boss_avatar')
    screen = cv2_utils.read_image(os.path.join(_IMG_DIR, file_name))
    _cv_result, results = checker.run_task(screen, task)
    return dict(results)


def test_boss_avatar_task_registered() -> None:
    """任务已注册 间隔 10 秒 状态名固定。"""
    task = next(t for t in DETECTION_TASKS if t.task_id == 'boss_avatar')
    assert task.pipeline_name == 'boss_avatar_vesper'
    assert task.interval == 10.0
    assert [s.state_name for s in task.state_definitions] == [_STATE_NAME]


def test_boss_avatar_hit(test_context: TestContext) -> None:
    """薇斯珀头像命中。"""
    assert _run_task(test_context, 'vesper.jpg').get(_STATE_NAME) is True


def test_boss_avatar_other_boss_miss(test_context: TestContext) -> None:
    """其它首领头像不命中 命中不了时按清除处理。"""
    assert _run_task(test_context, 'other_boss.jpg').get(_STATE_NAME) is None
