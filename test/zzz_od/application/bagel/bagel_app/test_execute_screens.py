"""正式任务用真实节点和归档画面贯穿定位失败、结算、返回与额外入场。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_container import ContainerController
from test.harness.fixture_controller import enter_running_state, reset_running_state
from test.zzz_od.application.bagel.test_flows import BagelFixtureController

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEnum,
)
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from test.conftest import TestContext

    from one_dragon.base.geometry.point import Point

pytestmark = pytest.mark.usefixtures('no_round_wait')


class TaskController(ContainerController, BagelFixtureController):
    """复用容器控制器的输入记录和遮挡帧，以及贝果按键推进。"""

    def btn_press(self, key: str, press_time: float | None = None) -> None:
        """将退出按键与松键记录放在同一条时间序列中。"""
        self.trace.append((f'key:{key}', self.phase_idx, self.frames, time.time()))
        super().btn_press(key, press_time)

    def click(
        self, pos: Point | None = None, press_time: float = 0,
        pc_alt: bool = False, gamepad_key: str | None = None,
    ) -> bool:
        """点击保持真实区域判断，同时记录人工停止后的动作。"""
        self.trace.append(('click', self.phase_idx, self.frames, time.time()))
        return super().click(pos, press_time, pc_alt, gamepad_key)

    def screenshot(self, independent: bool = False) -> tuple[float, MatLike]:
        """指定的新局画面模拟人工停止，随后只有读取和松键可以发生。"""
        if self._phases[self.phase_idx].get('stop') and self.ctx.run_context.is_context_running:
            self.ctx.run_context._run_state = ApplicationRunContextStateEnum.STOP
            self.trace.append(('stop', self.phase_idx, self.frames, time.time()))
        return super().screenshot(independent)


def entry_phases() -> list[dict]:
    """入场点击全部使用归档截图；出生确认后只遮小地图制造真实定位失配。"""
    return [
        {'frame': ('贝果-研究站', '主界面-原生1080'),
         'exit': ('on_click_in', '贝果-研究站', '前往空洞')},
        {'frame': ('贝果-选图', '雅努斯高危-原生1080'),
         'exit': ('on_click_in', '贝果-选图', '前往备战')},
        {'frame': ('贝果-备战', '高危零携带-原生1080'),
         'exit': ('on_click_in', '贝果-备战', '前往空洞')},
        {'frame': ('贝果-入场确认', '高危零投资-原生1080'),
         'exit': ('on_click_in', '贝果-入场确认', '零投资前往空洞')},
        {'frame': ('贝果-局内', '高危A出生-原生1080'), 'exit': ('on_polls', 2)},
        {'frame': ('贝果-局内', '高危A出生-原生1080'), 'hide': ('定位小地图',), 'key': 'esc'},
        {'frame': ('贝果-局内', '暂停菜单-原生1080'),
         'exit': ('on_click_in', '战斗-菜单', '按钮-退出战斗')},
        {'frame': ('贝果-退出确认', '主动退出-原生1080'),
         'exit': ('on_click_in', '贝果-退出确认', '确认')},
        {'frame': ('贝果-结算', '高危空局失败-原生1080'),
         'exit': ('on_click_in', '贝果-结算', '继续')},
    ]


@pytest.mark.parametrize('manual_stop', [False, True], ids=['exhausted', 'human-stop'])
def test_failed_round_settles_before_real_reentry(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, manual_stop: bool,
) -> None:
    """不替换操作结果或释放函数，验证定位耗尽及人工停止的真实框架出口。"""
    config = BagelConfig(99, 'standalone')
    config.max_failure_retries = 1
    config.auto_clean_warehouse = False
    record = BagelRunRecord(99)
    controller = TaskController(test_context)
    first = entry_phases()
    second = entry_phases()
    if manual_stop:
        arrival = next(index for index, phase in enumerate(second) if phase['frame'][0] == '贝果-局内')
        second[arrival] = {'frame': ('贝果-局内', '高危A出生-原生1080'), 'stop': True}
        second = second[:arrival + 1]
    controller.set_phases([
        *first,
        {'frame': ('贝果-仓库', '带物资仓库-r07-117s'),
         'exit': ('on_click_in', '贝果-仓库', '放入仓库')},
        {'frame': ('贝果-仓库', '入仓后安全箱空-r07-118s'),
         'exit': ('on_click_in', '贝果-仓库', '返回研究站')},
        {'frame': ('贝果-研究站', '返回研究站达塔前-原生1080'), 'on': 'f'},
        {'frame': ('贝果-研究站', '达塔对话-原生1080'),
         'exit': ('on_click_in', '贝果-研究站', '出发对话')},
        *second,
        *([] if manual_stop else [{'frame': ('贝果-仓库', '空局仓库-原生1080')}]),
    ])
    monkeypatch.setattr(test_context, 'controller', controller)

    def release_key(key: object) -> None:
        """记录真实清理函数对底层键盘接口的调用。"""
        label = getattr(key, 'char', None) or str(key)
        controller.trace.append((f'key.release:{label}', controller.phase_idx, controller.frames, time.time()))

    def release_mouse(button: object) -> None:
        """鼠标拖拽松开与键盘松开均须在退出动作之前发生。"""
        label = getattr(button, 'name', None) or str(button)
        controller.trace.append((f'mouse.release:{label}', controller.phase_idx, controller.frames, time.time()))

    controller.keyboard_controller.keyboard.release.side_effect = release_key
    controller.keyboard_controller.mouse.release.side_effect = release_mouse
    app = BagelApp(test_context, config, record)
    enter_running_state(test_context)
    try:
        result = app.execute()
        assert not result.success, result.status
        assert app.failure_retries_used == 1 and app.success_rounds == 0
        assert controller.phase_idx == len(controller._phases) - 1
        assert '小地图持续无法定位' in record.get('retry_summary')['failures'][0]['reason']
        trace = [event[0] for event in controller.trace]
        first_exit = trace.index('key:esc')
        required_releases = {'key.release:w', 'key.release:f', 'mouse.release:left'}
        assert required_releases <= set(trace[:first_exit])
        assert controller.click_hit_area('贝果-仓库', '放入仓库')
        if manual_stop:
            assert result.status == '人工结束'
            after_stop = trace[trace.index('stop') + 1:]
            assert required_releases <= set(after_stop)
            assert not any(event in ('click', 'f', 'w', 'turn', 'key:esc') for event in after_stop)
        else:
            assert '整体重试已用 1/1，已完成仓库结算' in result.status
            assert app.defeat_rounds == 2
    finally:
        reset_running_state(test_context, app)
