"""ZzzBackendContext 生命周期与就绪校验的单元测试。

测试使用 MagicMock 伪造 ZContext，避免触发真实的 onnx 模型加载。
"""

from unittest.mock import MagicMock

import pytest

from zzz_od.backend.backend_context import BackendNotReadyError, ZzzBackendContext


def _backend(ready: bool = True, controller: MagicMock | None = None) -> ZzzBackendContext:
    """构造一个使用伪造 ctx 的 ZzzBackendContext。

    Args:
        ready: ctx.ready_for_application 的取值，默认 True。
        controller: ctx.controller 的取值，默认 None。

    Returns:
        绑定了伪造 ctx 的 ZzzBackendContext 实例。
    """
    ctx = MagicMock()
    ctx.ready_for_application = ready
    ctx.controller = controller
    return ZzzBackendContext(ctx)


@pytest.mark.asyncio
async def test_start_runs_init_in_thread() -> None:
    """start() 应当在线程池中调用 ctx.init() 完成初始化。"""
    ctx = MagicMock()
    backend = ZzzBackendContext(ctx)
    await backend.start()
    ctx.init.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_runs_after_app_shutdown_in_thread() -> None:
    """shutdown() 应当在线程池中调用 ctx.after_app_shutdown() 释放资源。"""
    ctx = MagicMock()
    backend = ZzzBackendContext(ctx)
    await backend.shutdown()
    ctx.after_app_shutdown.assert_called_once()


def test_ensure_ready_raises_when_not_ready() -> None:
    """ctx 未就绪时，_ensure_ready() 应抛出 BackendNotReadyError。"""
    backend = _backend(ready=False)
    with pytest.raises(BackendNotReadyError):
        backend._ensure_ready()


def test_check_window_returns_status_no_rect() -> None:
    game_win = MagicMock(
        win_title="绝区零", is_win_valid=True, is_win_active=False, is_win_scale=True, win_rect=None
    )
    backend = _backend(ready=True, controller=MagicMock(game_win=game_win))
    status = backend.check_window()
    assert status.win_title == "绝区零"
    assert status.is_win_valid is True
    assert status.x is None


def test_check_window_with_rect() -> None:
    rect = MagicMock(x1=1, y1=2, width=3, height=4)
    game_win = MagicMock(win_title="t", is_win_valid=True, is_win_active=True, is_win_scale=True, win_rect=rect)
    backend = _backend(ready=True, controller=MagicMock(game_win=game_win))
    status = backend.check_window()
    assert (status.x, status.y, status.width, status.height) == (1, 2, 3, 4)


def test_capture_returns_image() -> None:
    controller = MagicMock()
    controller.is_game_window_ready = True
    fake_img = object()
    controller.get_screenshot.return_value = fake_img
    controller.fill_uid_black.return_value = fake_img
    backend = _backend(ready=True, controller=controller)
    # capture 经 fill_uid_black 打码后返回(对齐 controller.screenshot)
    assert backend.capture() is fake_img
    controller.get_screenshot.assert_called_once_with(independent=False)
    controller.fill_uid_black.assert_called_once_with(fake_img)


def test_capture_raises_when_window_not_ready() -> None:
    controller = MagicMock()
    controller.is_game_window_ready = False
    backend = _backend(ready=True, controller=controller)
    with pytest.raises(BackendNotReadyError):
        backend.capture()


def test_analyze_maps_ocr_results() -> None:
    r1 = MagicMock(data="体力", x=1, y=2, w=3, h=4)
    r2 = MagicMock(data="设定", x=5, y=6, w=7, h=8)
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = object()
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = [r1, r2]
    backend = ZzzBackendContext(ctx)
    result = backend.analyze()
    assert result.success is True
    assert [t.text for t in result.ocr_texts] == ["体力", "设定"]
    assert result.ocr_texts[0].width == 3
    assert result.vision_hint is not None  # success 时带能力边界提示


def test_analyze_returns_error_when_screenshot_none() -> None:
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = None
    backend = _backend(ready=True, controller=controller)
    result = backend.analyze()
    assert result.success is False
    assert "截图失败" in (result.error or "")
    assert result.vision_hint is None  # 失败时不带提示


def test_analyze_returns_screens_and_writes_back_on_precise(monkeypatch) -> None:
    """analyze 精准命中 → 返回 screens[0].is_precise=True,并回写 current_screen_name。"""
    import zzz_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    # mock find_screen_matches 返精准
    precise = ScreenMatch(screen_name='菜单', is_precise=True, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [precise])
    # mock ocr_service 返空(ocr_texts 走全图 OCR)
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []

    result = backend.analyze()
    assert result.success is True
    assert len(result.screens) == 1
    assert result.screens[0].is_precise is True
    # 回写
    backend.ctx.screen_loader.update_current_screen_name.assert_called_once_with('菜单')


def test_analyze_no_precise_does_not_write_back(monkeypatch) -> None:
    """analyze 无精准(模糊 top_n)→ 不回写 current_screen_name。"""
    import zzz_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    fuzzy = ScreenMatch(screen_name='某画面', is_precise=False, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [fuzzy])
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []

    result = backend.analyze()
    assert result.success is True
    assert result.screens[0].is_precise is False
    backend.ctx.screen_loader.update_current_screen_name.assert_not_called()


def test_analyze_exception_no_writeback(monkeypatch) -> None:
    """匹配中途异常 → success=False, screens=[], 不回写。"""
    import zzz_od.backend.backend_context as bc

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    def boom(ctx, screen, top_n=5):
        raise RuntimeError('ocr boom')
    monkeypatch.setattr(bc, 'find_screen_matches', boom)

    result = backend.analyze()
    assert result.success is False
    assert result.screens == []
    assert result.error is not None
    backend.ctx.screen_loader.update_current_screen_name.assert_not_called()


def test_start_run_delegates_to_run_slot() -> None:
    """start_run 应委托 run_slot._start(op 路径)，返回 (ok, future) 元组。

    覆盖旧的 enter_game 用例：不再有同步 enter_game 方法，运行由
    run_slot 异步派发；此处直接 mock run_slot，验证透传与返回结构。
    """
    from concurrent.futures import Future

    backend = _backend(ready=True)
    fut: Future = Future()
    fut.set_result(object())
    backend.run_slot = MagicMock()
    backend.run_slot._start.return_value = (True, fut)

    def _factory(_ctx: object) -> object:
        return object()

    ok, future = backend.start_run("mcp", _factory)
    assert ok is True
    assert future is fut
    backend.run_slot._start.assert_called_once_with(
        "mcp", op_factory=_factory, display_name=None
    )


def test_query_status_delegates_to_run_slot() -> None:
    """query_status 应委托 run_slot._query_status 返回 RunStatusResult。"""
    from zzz_od.backend.schemas import RunStatusResult

    expected = RunStatusResult(state="idle", source=None, app=None,
                               started_at=None, duration_seconds=None)
    backend = _backend(ready=True)
    backend.run_slot = MagicMock()
    backend.run_slot._query_status.return_value = expected

    assert backend.query_status() is expected
    backend.run_slot._query_status.assert_called_once()


def test_stop_delegates_to_run_slot() -> None:
    """stop 应封装 run_slot._stop，无运行时返回 {stopped: False, error}。"""
    backend = _backend(ready=True)
    backend.run_slot = MagicMock()
    backend.run_slot._stop.return_value = (False, None)

    assert backend.stop() == {"stopped": False, "error": "当前无运行"}
    backend.run_slot._stop.assert_called_once()


def test_list_applications_no_refresh(monkeypatch) -> None:
    """list_applications 是只读路径,不应调用 _refresh_runtime_config。"""
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.standalone_app_config.active_app_id = ''
    ctx.standalone_app_config.app_list = []
    group_config = MagicMock()
    group_config.app_list = []
    ctx.app_group_manager.get_one_dragon_group_config.return_value = group_config
    ctx.run_context.is_app_registered.return_value = False
    ctx.run_context.default_group_apps = []
    ctx.current_instance_idx = 0
    backend = ZzzBackendContext(ctx)

    called: list = []
    monkeypatch.setattr(backend, '_refresh_runtime_config', lambda: called.append(True))

    result = backend.list_applications()
    assert result.applications == []
    assert called == []                          # 只读路径不刷新配置


def test_list_predefined_teams_filters_placeholder() -> None:
    """list_predefined_teams 过滤 TeamConfig 自动补的占位,只返回真实队。"""
    from zzz_od.config.team_config import PredefinedTeamInfo
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.current_instance_idx = 2
    ctx.team_config.team_list = [
        PredefinedTeamInfo(0, '冰雅狼苍', '全配队通用', ['a', 'b', 'c']),
        PredefinedTeamInfo(1, '火队', '火属性', ['d', 'e']),
    ] + [PredefinedTeamInfo(i, f'编队{i + 1}', '全配队通用', []) for i in range(2, 20)]
    ctx.team_config.get.return_value = [{}, {}]    # yml 真实队数 = 2(后 18 是补的占位)
    backend = ZzzBackendContext(ctx)
    backend._get_shiyu_defense_config = lambda: None  # 无防卫战配置(假 agent 不在 AgentEnum → weakness 空)

    result = backend.list_predefined_teams()
    assert result.current_instance_idx == 2
    assert len(result.teams) == 2                   # 过滤掉 18 个占位
    assert result.teams[0].idx == 0
    assert result.teams[0].name == '冰雅狼苍'
    assert result.teams[0].auto_battle == '全配队通用'
    assert result.teams[1].agent_id_list == ['d', 'e', 'unknown']  # 补 unknown 到 3
    assert result.teams[0].weakness_list == []      # 假 agent('a'/'b'/'c')不在 AgentEnum → 空
    assert result.teams[0].agent_name_list == ['a', 'b', 'c']  # 假 agent → 用原 id


def test_weakness_defense_priority() -> None:
    """_weakness_of_team:防卫战配了 weakness → 用它(中文),不走角色属性。"""
    from zzz_od.application.shiyu_defense.shiyu_defense_config import ShiyuDefenseTeamConfig
    from zzz_od.config.team_config import PredefinedTeamInfo
    from zzz_od.game_data.agent import DmgTypeEnum
    ctx = MagicMock()
    ctx.ready_for_application = True
    backend = ZzzBackendContext(ctx)
    defense_cfg = MagicMock()
    defense_cfg.get_config_by_team_idx.return_value = ShiyuDefenseTeamConfig(0, [DmgTypeEnum.FIRE, DmgTypeEnum.ICE])
    backend._get_shiyu_defense_config = lambda: defense_cfg

    # anby 是电属性,但防卫战配了 火/冰 → 用防卫战
    team = PredefinedTeamInfo(0, '火队', '全配队通用', ['anby'])
    assert backend._weakness_of_team(team) == ['火属性', '冰属性']


def test_weakness_defense_all_unknown_falls_back() -> None:
    """_weakness_of_team:防卫战配了但全是 UNKNOWN(过滤后空)→ 回退角色属性。"""
    from zzz_od.application.shiyu_defense.shiyu_defense_config import ShiyuDefenseTeamConfig
    from zzz_od.config.team_config import PredefinedTeamInfo
    from zzz_od.game_data.agent import DmgTypeEnum
    ctx = MagicMock()
    ctx.ready_for_application = True
    backend = ZzzBackendContext(ctx)
    defense_cfg = MagicMock()
    defense_cfg.get_config_by_team_idx.return_value = ShiyuDefenseTeamConfig(0, [DmgTypeEnum.UNKNOWN])
    backend._get_shiyu_defense_config = lambda: defense_cfg

    # 防卫战配了 [UNKNOWN](过滤后空)→ 回退角色:anby 电属性
    team = PredefinedTeamInfo(0, '队', '全配队通用', ['anby'])
    assert backend._weakness_of_team(team) == ['电属性']


def test_weakness_fallback_to_agent_dmg() -> None:
    """_weakness_of_team:防卫战没配 → 取角色伤害属性(中文,去重,跳 unknown)。"""
    from zzz_od.config.team_config import PredefinedTeamInfo
    ctx = MagicMock()
    ctx.ready_for_application = True
    backend = ZzzBackendContext(ctx)
    backend._get_shiyu_defense_config = lambda: None

    # anby(电)重复 + ben(火)+ unknown → [电属性, 火属性](去重:重复电属性只算一次)
    team = PredefinedTeamInfo(0, '队', '全配队通用', ['anby', 'anby', 'ben', 'unknown'])
    assert backend._weakness_of_team(team) == ['电属性', '火属性']


def test_agent_name_list_chinese() -> None:
    """agent_name_list:真 agent 取中文名,unknown/未注册取原 id。"""
    from zzz_od.config.team_config import PredefinedTeamInfo
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.current_instance_idx = 0
    ctx.team_config.team_list = [PredefinedTeamInfo(0, '队', '全配队通用', ['anby', 'ben', 'unknown', 'fake_id'])]
    ctx.team_config.get.return_value = [{}]    # raw_count=1
    backend = ZzzBackendContext(ctx)
    backend._get_shiyu_defense_config = lambda: None

    result = backend.list_predefined_teams()
    assert result.teams[0].agent_name_list == ['安比', '本', 'unknown', 'fake_id']


def test_get_shiyu_defense_config_unregistered_returns_none() -> None:
    """_get_shiyu_defense_config:防卫战 app 未注册 → None,且不调 get_config。"""
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.run_context.is_app_registered.return_value = False
    backend = ZzzBackendContext(ctx)

    assert backend._get_shiyu_defense_config() is None
    ctx.run_context.get_config.assert_not_called()  # 未注册就不去 get_config


def test_get_shiyu_defense_config_registered_returns_config() -> None:
    """_get_shiyu_defense_config:防卫战 app 已注册 → 透传 get_config 结果。"""
    from zzz_od.application.shiyu_defense import shiyu_defense_const
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.run_context.is_app_registered.return_value = True
    fake_cfg = object()
    ctx.run_context.get_config.return_value = fake_cfg
    backend = ZzzBackendContext(ctx)

    result = backend._get_shiyu_defense_config()
    assert result is fake_cfg
    _, kwargs = ctx.run_context.get_config.call_args
    assert kwargs['app_id'] == shiyu_defense_const.APP_ID


def test_get_shiyu_defense_config_registered_propagates_load_error() -> None:
    """_get_shiyu_defense_config:已注册但 get_config 抛异常 → 向上抛,不静默吞。"""
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.run_context.is_app_registered.return_value = True
    ctx.run_context.get_config.side_effect = RuntimeError('yaml boom')
    backend = ZzzBackendContext(ctx)

    with pytest.raises(RuntimeError, match='yaml boom'):
        backend._get_shiyu_defense_config()


def test_close_game_delegates() -> None:
    """close_game 应委托 controller.close_game()。"""
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.close_game.return_value = None
    backend = _backend(ready=True, controller=controller)
    msg = backend.close_game()
    controller.close_game.assert_called_once()
    assert msg == '已发送关闭游戏信号,可用 check_game_window 验证'


def test_analyze_save_image_persists_and_returns_path(monkeypatch) -> None:
    """analyze(save_image=True) 实时模式:存盘 + screenshot_path 回传路径。"""
    import numpy as np
    import zzz_od.backend.backend_context as bc

    saved_args: list = []

    def fake_save(image):
        saved_args.append(image)
        return '/tmp/fake_screenshot.png'

    monkeypatch.setattr(bc, '_save_screenshot', fake_save)
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = []
    backend = ZzzBackendContext(ctx)
    result = backend.analyze(save_image=True)
    assert result.success is True
    assert result.screenshot_path == '/tmp/fake_screenshot.png'
    assert len(saved_args) == 1


def test_analyze_save_image_false_does_not_persist(monkeypatch) -> None:
    """analyze() 默认 save_image=False:不存盘,screenshot_path=None。"""
    import zzz_od.backend.backend_context as bc

    called: list = []
    monkeypatch.setattr(bc, '_save_screenshot', lambda img: called.append(img) or '/tmp/x.png')
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = object()
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = []
    backend = ZzzBackendContext(ctx)
    result = backend.analyze()
    assert result.success is True
    assert result.screenshot_path is None
    assert called == []


def test_analyze_offline_ignores_save_image(monkeypatch, tmp_path) -> None:
    """analyze(screenshot=path) 离线模式:save_image 被忽略,screenshot_path=None。"""
    import cv2
    import numpy as np
    import zzz_od.backend.backend_context as bc

    called: list = []
    monkeypatch.setattr(bc, '_save_screenshot', lambda img: called.append(img) or '/tmp/x.png')
    img_path = tmp_path / 'shot.png'
    cv2.imwrite(str(img_path), np.zeros((4, 4, 3), dtype=np.uint8))
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.ocr_service.get_ocr_result_list.return_value = []
    backend = ZzzBackendContext(ctx)
    result = backend.analyze(screenshot=str(img_path), save_image=True)
    assert result.success is True
    assert result.screenshot_path is None
    assert called == []


def test_analyze_save_image_capture_fails_no_path() -> None:
    """实时捕获失败(get_screenshot None)→ success=False,screenshot_path=None。"""
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = None
    backend = _backend(ready=True, controller=controller)
    result = backend.analyze(save_image=True)
    assert result.success is False
    assert result.screenshot_path is None


def test_analyze_save_image_then_ocr_fail_returns_path(monkeypatch) -> None:
    """存盘成功但后续 OCR 异常 → success=False, screenshot_path 仍回传(排障)。"""
    import numpy as np
    import zzz_od.backend.backend_context as bc

    monkeypatch.setattr(bc, '_save_screenshot', lambda img: '/tmp/fake.png')
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.side_effect = RuntimeError('ocr boom')
    backend = ZzzBackendContext(ctx)
    result = backend.analyze(save_image=True)
    assert result.success is False
    assert result.screenshot_path == '/tmp/fake.png'
    assert result.error is not None
