"""EnterGame 多节点流程测试（fixture 驱动）。

覆盖 EnterGame 的 CN 已登录态 happy-path：

    打开游戏/ready →(click 点击进入游戏)→ 登录服务器中 →(poll)
    → 登录成功 →(poll)→ 加载画面/港口工厂旧址 →(poll)→ 大世界/普通 (terminal)

验证：
- op 完整跑完 ``execute()`` 并到达大世界（成功）；
- 记录到了 ``点击进入游戏`` 的流程 click。

恢复性 click（如 ``国服-返回按钮``）的门控（``on_click_in`` 只认流程 click）按
§4.2 实现，但 happy-path 不会实际触发该恢复 click——由 :class:`TestOnClickInGating`
专项单测直接覆盖，本流程不重复断言。

不测 OpenGame/OpenAndEnterGame（写注册表 + 拉 exe，§5）——
``is_game_window_ready=True`` 绕过框架注入的“检测游戏窗口→打开游戏”前置链。
"""

from __future__ import annotations

import pytest
from test.conftest import TestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)

from one_dragon.base.config.basic_game_config import TypeInputWay
from one_dragon.base.geometry.point import Point
from zzz_od.operation.enter_game.enter_game import EnterGame


class _WatchedEnterGame(WatchdogOperationMixin, EnterGame):
    """带看门狗的 EnterGame（看门狗通过混入覆盖 _execute_one_round）。"""


def _build_phases() -> list[dict]:
    """构造 CN 已登录态 happy-path 剧本。

    - ready：唯一流程 click 是 ``点击进入游戏``（在 check_enter_click_status 节点
      触发）；同节点的 check_screen 若误识别到 ``国服-账号密码进入游戏-新`` 会点
      ``国服-返回按钮``（恢复 click），用 ``on_click_in`` 只认流程 click。
    - 登录服务器中 / 登录成功：游戏自动流转，靠 screenshot 轮询推进（on_polls）。
    - 加载画面 / 大世界：同样轮询推进；大世界是 terminal，无 exit。
    """
    return [
        {
            'frame': ('打开游戏', 'ready'),
            # 只认落在「点击进入游戏」area 内的 click（流程 click）。
            'exit': ('on_click_in', '打开游戏', '点击进入游戏'),
        },
        {
            'frame': ('打开游戏', '登录服务器中'),
            'exit': ('on_polls', 1),
        },
        {
            'frame': ('打开游戏', '登录成功'),
            'exit': ('on_polls', 1),
        },
        {
            'frame': ('加载画面', '港口工厂旧址'),
            'exit': ('on_polls', 1),
        },
        {
            'frame': ('大世界', '普通'),
            # terminal：不推进。
        },
    ]


@pytest.fixture()
def fixture_controller(
    test_context: TestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """注入 FixtureController 并 pin 键盘输入方式（避免写真实 OS 剪贴板，§4.3）。

    用 ``monkeypatch.setattr`` 改写 ``controller``/``type_input_way``，pytest 在
    测试结束后自动还原——避免污染 session 级 ``test_context``（否则后续测试拿到
    FixtureController 而非 MockController，且其 screenshot 忽略 mock_screenshot）。
    """
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    # 强制走 keyboard.type 分支，避免 PcClipboard.copy_and_paste 写真实剪贴板。
    monkeypatch.setattr(
        test_context.game_config,
        'type_input_way',
        TypeInputWay.INPUT.value.value,
    )
    return ctrl


class TestEnterGameFlow:
    """EnterGame 端到端流程测试。"""

    def test_enter_game_reaches_big_world(
        self,
        test_context: TestContext,
        fixture_controller: FixtureController,
    ) -> None:
        # 载入剧本
        fixture_controller.set_phases(_build_phases())

        # CN 区服；无账号密码 → force_login=False，直接走已登录态进入。
        test_context.game_account_config.game_region = 'cn'

        op = _WatchedEnterGame(test_context, switch=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 核心断言：op 成功到达大世界。
        assert result.success, (
            f'EnterGame 未成功完成：status={result.status}'
            f'；最后 phase_idx={fixture_controller.phase_idx}'
            f'；recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert result.status == '大世界', (
            f'期望到达大世界，实际 status={result.status}'
        )

        # 关键流程 click 被记录到：「点击进入游戏」area 内至少一次 click。
        assert fixture_controller.click_hit_area('打开游戏', '点击进入游戏'), (
            '未记录到「点击进入游戏」流程 click：'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )

        # 健全性：op 已消费到剧本末 phase（大世界）。
        assert fixture_controller.phase_idx == len(_build_phases()) - 1, (
            f'剧本未推进到末 phase：phase_idx={fixture_controller.phase_idx}'
        )


def _fmt_clicks(clicks: list) -> str:
    return ', '.join(f'({p.x},{p.y})' for p in clicks) or '<empty>'


class TestOnClickInGating:
    """``FixtureController`` 的 ``on_click_in`` 门控专项单测（§4.2）。

    happy-path 流程不会实际触发恢复性 click（``国服-返回按钮`` 在 ``ready`` fixture
    上不会命中），这里直接驱动 :meth:`FixtureController.click` 锁定门控判定：
    落在声明 region 内才推进 phase，region 外只记录不推进。无需跑完整 op。
    """

    def test_on_click_in_region_gating(self, test_context: TestContext) -> None:
        # 直接构造 FixtureController（不经过 fixture_controller fixture，不改写
        # ctx.controller，零污染）。frame 仅 screenshot() 时才会读取，本用例不触达。
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        ctrl.set_phases(
            [
                # phase 0：只在 [100,100]-[200,200] 矩形内 click 才推进。
                {
                    'frame': ('打开游戏', 'ready'),
                    'exit': ('on_click_in', [100, 100, 200, 200]),
                },
                # phase 1：terminal，无 exit。
                {'frame': ('打开游戏', '登录服务器中')},
            ]
        )

        # region 外 click：不应推进，但应被记录。
        ctrl.click(Point(500, 500))
        assert ctrl.phase_idx == 0, 'region 外 click 不应推进 phase'
        assert len(ctrl.recorded_clicks) == 1, 'region 外 click 应被记录'
        assert (ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y) == (500, 500)

        # region 内 click：应推进到 phase 1。
        ctrl.click(Point(150, 150))
        assert ctrl.phase_idx == 1, 'region 内 click 应推进 phase'
        assert len(ctrl.recorded_clicks) == 2
