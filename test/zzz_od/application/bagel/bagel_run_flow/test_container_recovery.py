"""容器靠近、交互和恢复通过公共执行器完成，断言实际输入与新帧顺序。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test.harness.bagel_container import (
    WatchedFlow,
    execute,
    phases,
    prepare,
)

if TYPE_CHECKING:
    from pathlib import Path

    from cv2.typing import MatLike
    from test.conftest import TestContext

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.mark.parametrize('target', ['box', 'safe'])
@pytest.mark.parametrize('displacement', [-2.5, 2.5])
def test_prompt_disappears_after_release_requires_fresh_recovery(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str, displacement: float,
) -> None:
    """前后位移均读取松键后新图，短步恢复并再次停稳，才能按首次 F。"""
    prompt, missing, panel = phases(target)
    controller, op, events = prepare(test_context, monkeypatch, target, [
        {**prompt, 'on': 'release'}, {**missing, 'on': 'w'}, {**prompt, 'on': 'f'}, panel,
    ], displacement=displacement)
    controller.stale_after_release = True
    result = execute(op)
    assert result.success, (result.status, result.data)
    actions = [e for e in controller.trace if e[0] in ('w', 'f')]
    assert [e[0] for e in actions] == ['w', 'f']
    assert actions[0][1] == 1 and actions[1][1] == 2
    assert actions[0][2] > next(e[2] for e in controller.trace if e[0] == 'stale')
    release = next(e for e in controller.trace if e[0] == 'release' and e[1] == 2)
    assert actions[1][2] > release[2] and actions[1][3] - release[3] >= 0.5
    assert len([e for e in events if e['kind'] == 'done']) == 2


def test_white_dove_uses_real_location_to_restore_prompt(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """白鸽存档真实配准贯穿恢复；遮掉提示不替换定位或成功结果。"""
    prompt, missing, panel = phases('box')
    controller, op, _ = prepare(test_context, monkeypatch, 'box', [
        {**prompt, 'on': 'release'}, {**missing, 'on': 'w'}, {**prompt, 'on': 'f'}, panel,
    ])
    result = execute(op)
    assert result.success, (result.status, result.data)
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['w', 'f']


@pytest.mark.parametrize('target', ['box', 'safe'])
@pytest.mark.parametrize('drops', [False, True])
def test_first_f_failure_retries_or_reapproaches(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str, drops: bool,
) -> None:
    """提示持续存在补按，提示消失才重建导航；开箱次数跨子操作共享。"""
    prompt, missing, panel = phases(target)
    middle = [{**missing, 'on': 'w'}] if drops else []
    controller, op, events = prepare(test_context, monkeypatch, target, [
        {**prompt, 'on': 'f'}, *middle, {**prompt, 'on': 'f'}, panel,
    ], displacement=2.5)
    result = execute(op)
    assert result.success, (result.status, result.data)
    assert [e[0] for e in controller.trace if e[0] in ('f', 'w')] == (['f', 'w', 'f'] if drops else ['f', 'f'])
    assert len([e for e in events if e['kind'] == 'done']) == 2


@pytest.mark.parametrize('target', ['box', 'safe'])
@pytest.mark.parametrize('succeeds', [False, True])
def test_third_f_is_allowed_fourth_is_rejected(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str, succeeds: bool,
) -> None:
    """第三次可以进入面板，继续无效时失败且不发送第四次 F。"""
    prompt, _, panel = phases(target)
    script = [{**prompt, 'on': 'f'}, {**prompt, 'on': 'f'}, {**prompt, 'on': 'f'}]
    script.append(panel if succeeds else prompt)
    controller, op, _ = prepare(test_context, monkeypatch, target, script)
    result = execute(op)
    assert result.success == succeeds, (result.status, result.data)
    assert len([e for e in controller.trace if e[0] == 'f']) == 3
    assert not [e for e in controller.trace if e[0] == 'w']
    if not succeeds:
        assert result.status == op.STATUS_CONTAINER_FAILED
        assert result.data == '容器开箱交互已达3次上限'


@pytest.mark.parametrize('target', ['box', 'safe'])
@pytest.mark.parametrize('succeeds', [False, True])
def test_second_reapproach_is_allowed_third_is_rejected(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str, succeeds: bool,
) -> None:
    """连续两次停步丢提示可以恢复，第三次丢提示不能再移动。"""
    prompt, missing, panel = phases(target)
    script = [
        {**prompt, 'on': 'release'}, {**missing, 'on': 'w'},
        {**prompt, 'on': 'release'}, {**missing, 'on': 'w'},
    ]
    script.extend([{**prompt, 'on': 'f'}, panel] if succeeds else [{**prompt, 'on': 'release'}, missing])
    controller, op, _ = prepare(test_context, monkeypatch, target, script, displacement=2.5)
    result = execute(op)
    assert result.success == succeeds, (result.status, result.data)
    assert len([e for e in controller.trace if e[0] == 'w']) == 2
    assert len([e for e in controller.trace if e[0] == 'f']) == int(succeeds)
    if not succeeds:
        assert result.data == '容器重新靠近已达2次上限'


@pytest.mark.parametrize('target', ['box', 'safe'])
def test_selected_approach_does_not_open_container(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str,
) -> None:
    """只选靠近可以恢复并确认停稳，不能隐式开箱。"""
    prompt, missing, _ = phases(target)
    controller, op, _ = prepare(test_context, monkeypatch, target, [
        {**prompt, 'on': 'release'}, {**missing, 'on': 'w'}, prompt,
    ], selection='approach', displacement=2.5)
    result = execute(op)
    assert result.success, (result.status, result.data)
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['w']


@pytest.mark.parametrize('target', ['box', 'safe'])
def test_selected_interaction_cannot_restore_unselected_navigation(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str,
) -> None:
    """只选交互，首次 F 后提示消失也不能调用未选靠近或退出步骤。"""
    prompt, missing, _ = phases(target)
    controller, op, events = prepare(test_context, monkeypatch, target, [
        {**prompt, 'on': 'f'}, missing,
    ], selection='interact')
    result = execute(op)
    assert not result.success and result.status == op.STATUS_CONTAINER_FAILED
    assert '禁止隐式移动' in result.data
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['f']
    assert not [e for e in events if e['kind'] == 'done']


@pytest.mark.parametrize(('target', 'ready'), [
    ('box', '武备箱搜查中-r07'),
    ('safe', '电子保险箱第1轮小圈'),
    ('safe', '电子保险箱搜索完成'),
])
def test_existing_panel_skips_navigation_and_interaction(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str, ready: str,
) -> None:
    """正确搜查或解锁画面直接继续，禁止任何移动或开箱 F。"""
    controller, op, _ = prepare(test_context, monkeypatch, target, [
        {'frame': ('贝果-局内', ready), 'panel': True},
    ])
    result = execute(op)
    assert result.success, (result.status, result.data)
    assert not [e for e in controller.trace if e[0] in ('w', 'turn', 'f')]


@pytest.mark.parametrize('target', ['box', 'safe'])
def test_missing_location_releases_without_blind_movement(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str, tmp_path: Path,
) -> None:
    """松键后定位证据消失，不能借动作前位置补一步或按 F。"""
    from one_dragon.utils import debug_utils

    screenshot_dir = tmp_path / '.debug' / 'images'
    screenshot_dir.mkdir(parents=True)
    monkeypatch.setattr(debug_utils, 'get_debug_image_dir_path', lambda: str(screenshot_dir))
    prompt, missing, _ = phases(target)
    controller, op, _ = prepare(test_context, monkeypatch, target, [
        {**prompt, 'on': 'release'}, {**missing, 'hide': ('交互提示', '定位小地图')},
    ])
    result = execute(op)
    assert not result.success and result.status == op.STATUS_CONTAINER_FAILED
    assert '小地图定位失败' in result.data
    assert not [e for e in controller.trace if e[0] in ('w', 'turn', 'f')]
    assert any(e[0] == 'release' for e in controller.trace)
    assert list(tmp_path.glob('.debug/images/WatchedFlow_*.png'))


def test_thirty_seconds_includes_rebuilt_operations(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一次 F 后重建靠近，再进入交互；剩余时间不能重新起算。"""
    prompt, missing, panel = phases('box')
    controller, op, _ = prepare(test_context, monkeypatch, 'box', [
        {**prompt, 'on': 'f'}, {**missing, 'on': 'w'}, prompt,
    ], displacement=2.5)
    original_screenshot = controller.screenshot
    jump = False

    def screenshot(independent: bool = False) -> tuple[float, MatLike]:
        """恢复后的提示截图到达总时限，不能再发送第二次 F。"""
        nonlocal jump
        if controller.phase_idx == 2 and not jump:
            jump = True
            op.operation_start_time -= 30
        return original_screenshot(independent)

    monkeypatch.setattr(controller, 'screenshot', screenshot)
    result = execute(op)
    assert not result.success and result.data == '容器靠近与开箱恢复超过30秒'
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['f', 'w']


def test_pause_does_not_spend_time_or_refresh_input_budget(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """人工暂停的60秒不算恢复耗时，三次 F 上限仍有效。"""
    from one_dragon.base.operation.application.application_run_context import (
        ApplicationRunContextStateEnum,
    )

    prompt, _, _ = phases('box')
    controller, op, _ = prepare(test_context, monkeypatch, 'box', [prompt])

    def pause_and_resume() -> None:
        """使用框架暂停恢复入口，调整暂停起点模拟等待60秒。"""
        op.ctx.run_context._run_state = ApplicationRunContextStateEnum.PAUSE
        op._on_pause()
        op.operation_start_time -= 60
        op.pause_start_time -= 60
        op.ctx.run_context._run_state = ApplicationRunContextStateEnum.RUNNING
        op._on_resume()

    controller.pause_callback = pause_and_resume
    result = execute(op)
    assert not result.success and result.data == '容器开箱交互已达3次上限'
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['f', 'f', 'f']


@pytest.mark.parametrize('target', ['box', 'safe'])
def test_stop_and_f_recovery_share_two_approaches(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str,
) -> None:
    """停步恢复一次，F 后恢复一次，再次 F 丢提示不能获得第三次移动。"""
    prompt, missing, _ = phases(target)
    controller, op, events = prepare(test_context, monkeypatch, target, [
        {**prompt, 'on': 'release'}, {**missing, 'on': 'w'},
        {**prompt, 'on': 'f'}, {**missing, 'on': 'w'},
        {**prompt, 'on': 'f'}, missing,
    ], displacement=2.5)
    result = execute(op)
    assert not result.success and result.data == '容器重新靠近已达2次上限'
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['w', 'f', 'w', 'f']
    assert len([e for e in events if e['kind'] == 'done']) == 1


@pytest.mark.parametrize('target', ['box', 'safe'])
def test_wrong_container_panel_never_moves_or_interacts(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str,
) -> None:
    """另一容器的面板不能被当作已到达目标。"""
    other = 'safe' if target == 'box' else 'box'
    _, _, panel = phases(other)
    controller, op, _ = prepare(test_context, monkeypatch, target, [panel])
    result = execute(op)
    assert not result.success
    assert not [e for e in controller.trace if e[0] in ('w', 'turn', 'f')]


@pytest.mark.parametrize('target', ['box', 'safe'])
def test_prompt_without_f_icon_does_not_interact(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, target: str,
) -> None:
    """目标文字还在而 F 图标缺失，只选交互时前置不通过。"""
    prompt, _, _ = phases(target)
    controller, op, _ = prepare(test_context, monkeypatch, target, [
        {**prompt, 'hide': ('交互F键',)},
    ], selection='interact')
    result = execute(op)
    assert not result.success and 'F图标' in result.status
    assert not [e for e in controller.trace if e[0] in ('w', 'turn', 'f')]


def test_failed_container_does_not_start_store_step(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """选了收集也必须等容器成功打开，预算耗尽时不能继续下游。"""
    prompt, _, _ = phases('box')
    controller, prepared, events = prepare(test_context, monkeypatch, 'box', [prompt])
    store = next(s for s in prepared.flow.steps if s.action == 'store')
    op = WatchedFlow(test_context, prepared.flow, (*prepared.step_ids, store.id), on_event=events.append)
    result = execute(op)
    assert not result.success and result.data == '容器开箱交互已达3次上限'
    assert not [e for e in events if e['kind'] == 'start' and e['step_id'] == store.id]
    assert len([e for e in controller.trace if e[0] == 'f']) == 3


def test_controller_error_after_f_does_not_refresh_interaction_budget(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """输入发送后报错仍消耗次数，框架重试不能再发送第四次 F。"""
    prompt, _, _ = phases('box')
    controller, op, _ = prepare(test_context, monkeypatch, 'box', [prompt], selection='interact')
    original_press = controller.interact

    def failing_interact(
        press: bool = False, press_time: float | None = None, release: bool = False,
    ) -> None:
        """记录真实输入后模拟控制器异常。"""
        original_press(press=press, press_time=press_time, release=release)
        raise RuntimeError('测试控制器在发送F后报错')

    monkeypatch.setattr(controller, 'interact', failing_interact)
    result = execute(op)
    assert not result.success and result.data == '容器开箱交互已达3次上限'
    assert [e[0] for e in controller.trace if e[0] in ('w', 'f')] == ['f', 'f', 'f']
