"""LostVoidRunLevel 入口层武备选择重复交互处理 + 超时重开计时 测试。

背景(源码 ``lost_void_run_level.py``):入口层多个NPC相邻,交互判定角度>距离,完成武备选择后
再走向旁边感叹号容易重复命中同一个NPC → 无限循环到10分钟超时;且超时重开挑战后
``operation_start_time`` 不变,重试会立刻再次超时,3次重试全部浪费。

修复行为(已读源码确认;2026-08-26 按实测交互机制重写走位后同步更新):
1. ``handle_interact``:入口层构造 ``LostVoidChooseGear`` 时传共享名单 ``entry_gear_name_list``
   (非入口层传 None);子op成功后置 ``entry_gear_interact_done``;状态为 重复武备选择 时
   计数,达到3次把 ``感叹号`` 加入 ``had_been_list``(detect_to_go 按该列表过滤类别,
   之后不再追感叹号,直接找下层入口,最后兜底)。
2. ``move_after_interact``:入口层刚完成武备选择(``entry_gear_interact_done``)时调用
   ``_approach_remaining_interact_target``;未放弃感叹号时后退0.8秒让相邻感叹号进入画面,
   已放弃感叹号时保持前进(步长随重复次数加大)。
3. ``handle_find_target_fail``:重开挑战成功后 置 ``attempt_start_time`` 重新计时,并清空
   本层交互状态(had_been_list/interacted_target_key_list/entry_gear_* /ao_fei_li_ya_talked/
   stuck_state);``non_battle_check`` 的10分钟超时以 ``attempt_start_time``(为0时退回
   ``operation_start_time``)为起点。
4. ``try_interact`` 按键前闭环(完成过首次交互后即生效,不再只限放弃感叹号后):
   OCR 交互文本确认按下会命中谁 —— 文本是入口或没交互过的目标才按键;是已交互NPC或读不出时
   不按,``_steer_towards_other_interact_icon`` 用当前标签x排除已瞄准图标后朝剩余最近感叹号
   迈步(放弃感叹号找门阶段 prefer_entry=True 直接朝下层入口图标迈步);重试上限8次,
   达上限时标签明确是已交互NPC则后退换角度重新接近(round_fail 重复交互对象),
   只有读不出才直接按键兜底。
5. ``after_interact``:入口层三个NPC(两武备+研究员)都交互完成后,主动把 感叹号 加入
   ``had_been_list``,直接前往下层入口。

fixture:``迷失之地-武备选择/初始战术棱镜方案``、``迷失之地-大世界/玛琳前-以太稳定``(均已有)。
"""
import time
from unittest.mock import Mock, patch

from test.conftest import TestContext

from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_gear import (
    LostVoidChooseGear,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_interact_target_const import (
    LostVoidInteractTarget,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)
from zzz_od.operation.challenge_mission.restart_in_battle import RestartInBattle


def _make_op(test_context: TestContext, region: LostVoidRegionType = LostVoidRegionType.ENTRY) -> LostVoidRunLevel:
    return LostVoidRunLevel(test_context, region)


def test_handle_interact_repeat_three_times_ignores_exclamation(test_context: TestContext) -> None:
    """入口层重复武备选择达到3次 → had_been_list 加入 感叹号(本层不再追感叹号,最后兜底)。"""
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-武备选择', '初始战术棱镜方案')
    op.screenshot()

    op.entry_door_block_times = 5  # 应在每次重复退出后清零
    repeated = OperationResult(success=True, status=LostVoidChooseGear.STATUS_REPEATED)
    with patch.object(LostVoidChooseGear, 'execute', return_value=repeated):
        op.handle_interact()
        assert op.entry_gear_repeat_times == 1
        assert op.entry_door_block_times == 0, '重复退出后应重置前进重试计数'
        assert '感叹号' not in op.had_been_list, '第1次重复不应放弃感叹号'
        assert op.entry_gear_interact_done, '完成武备选择交互后应置站位调整标志'

        test_context.mock_screen('迷失之地-武备选择', '初始战术棱镜方案')
        op.screenshot()
        op.handle_interact()
        assert op.entry_gear_repeat_times == 2
        assert '感叹号' not in op.had_been_list, '第2次重复不应放弃感叹号(转向策略还有机会)'

        test_context.mock_screen('迷失之地-武备选择', '初始战术棱镜方案')
        op.screenshot()
        op.handle_interact()

    assert op.entry_gear_repeat_times == 3
    assert '感叹号' in op.had_been_list, '第3次重复应放弃感叹号 直接前往下层入口'


def test_handle_interact_normal_success_no_repeat_count(test_context: TestContext) -> None:
    """入口层正常完成武备选择:置站位调整标志 不计重复次数。"""
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-武备选择', '初始战术棱镜方案')
    op.screenshot()

    normal = OperationResult(success=True, status='按钮-返回')
    with patch.object(LostVoidChooseGear, 'execute', return_value=normal):
        op.handle_interact()

    assert op.entry_gear_repeat_times == 0
    assert op.entry_gear_interact_done
    assert '感叹号' not in op.had_been_list


def test_handle_interact_passes_shared_list_only_at_entry(test_context: TestContext) -> None:
    """入口层把 entry_gear_name_list 传给子op;非入口层传 None(层中武备选择不启用)。"""
    for region, expect_shared in [
        (LostVoidRegionType.ENTRY, True),
        (LostVoidRegionType.COMBAT_GEAR, False),
    ]:
        op = _make_op(test_context, region)
        test_context.mock_screen('迷失之地-武备选择', '初始战术棱镜方案')
        op.screenshot()

        mock_cls = Mock()
        mock_cls.STATUS_REPEATED = LostVoidChooseGear.STATUS_REPEATED
        mock_cls.return_value.execute.return_value = OperationResult(success=True, status='按钮-返回')
        with patch(
            'zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level.LostVoidChooseGear',
            mock_cls,
        ):
            op.handle_interact()

        passed = mock_cls.call_args.kwargs['completed_name_list']
        if expect_shared:
            assert passed is op.entry_gear_name_list, '入口层应传共享名单'
        else:
            assert passed is None, '非入口层应传 None'


def test_move_after_interact_gear_done_adjusts_position(test_context: TestContext) -> None:
    """入口层刚完成武备选择(交互文本未识别出NPC名)→ 调整站位 并复位标志。"""
    op = _make_op(test_context)
    op.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)
    op.entry_gear_interact_done = True

    with patch.object(op, '_approach_remaining_interact_target') as mock_approach:
        op.move_after_interact()

    assert mock_approach.called
    assert not op.entry_gear_interact_done, '标志应在使用后复位'


def test_move_after_interact_without_gear_done_keeps_original(test_context: TestContext) -> None:
    """入口层非武备选择的感叹号交互(未置标志)→ 不调整站位(保持原行为)。"""
    op = _make_op(test_context)
    op.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)

    with patch.object(op, '_approach_remaining_interact_target') as mock_approach:
        op.move_after_interact()

    assert not mock_approach.called


def test_approach_after_gear_backs_off(test_context: TestContext) -> None:
    """未放弃感叹号时的站位调整:后退让相邻感叹号进入画面(不再贴近NPC/不查检测)。"""
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()

    with (
        patch.object(test_context.controller, 'move_s') as mock_back,
        patch.object(test_context.controller, 'move_w') as mock_forward,
    ):
        op._approach_remaining_interact_target()

    assert mock_back.called, '应后退让两个感叹号图标进入画面'
    assert not mock_forward.called


def _icon(class_name: str, center_x: float, height: float) -> Mock:
    """构造一个YOLO检测结果 mock(class_name/center/height)。"""
    icon = Mock()
    icon.detect_class.class_name = class_name
    icon.center = (center_x, 500)
    icon.height = height
    return icon


def _frame_with(*icons: Mock) -> Mock:
    frame = Mock()
    frame.results = list(icons)
    return frame


def test_steer_excludes_current_target_icon(test_context: TestContext) -> None:
    """转向:用当前标签x排除已瞄准的感叹号图标 朝剩余图标迈步(dx>60 → 向右横移)。"""
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()

    frame = _frame_with(
        _icon('0000-感叹号', 900, 80),   # 当前瞄准的NPC(标签x≈910) 应被排除
        _icon('0000-感叹号', 1400, 60),  # 剩余目标 dx=+440
    )
    with (
        patch.object(test_context.lost_void, 'detect_to_go', return_value=frame),
        patch.object(test_context.controller, 'move_w') as mock_forward,
        patch.object(test_context.controller, 'move_a') as mock_left,
        patch.object(test_context.controller, 'move_d') as mock_right,
    ):
        op._steer_towards_other_interact_icon(exclude_x=910)

    assert mock_forward.called, '应先前进收距离'
    assert mock_right.called and not mock_left.called, '剩余图标在右侧 应向右横移'


def test_steer_without_exclude_picks_nearest_icon(test_context: TestContext) -> None:
    """转向:无标签x时不排除 取最大(=最近)图标;dx<-60 → 向左横移。"""
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()

    frame = _frame_with(
        _icon('0000-感叹号', 860, 80),   # 最大=最近 dx=-100
        _icon('0000-感叹号', 1400, 40),
    )
    with (
        patch.object(test_context.lost_void, 'detect_to_go', return_value=frame),
        patch.object(test_context.controller, 'move_w') as mock_forward,
        patch.object(test_context.controller, 'move_a') as mock_left,
        patch.object(test_context.controller, 'move_d') as mock_right,
    ):
        op._steer_towards_other_interact_icon(exclude_x=None)

    assert mock_forward.called
    assert mock_left.called and not mock_right.called, '最近图标在左侧 应向左横移'


def test_steer_prefer_entry_targets_entry_icon(test_context: TestContext) -> None:
    """转向(找门):prefer_entry=True 时无视感叹号 直接朝下层入口图标迈步。"""
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()

    frame = _frame_with(
        _icon('0000-感叹号', 900, 80),        # 已交互NPC的图标 不应作为目标
        _icon('0002-战斗-鸣徽', 1300, 50),    # 下层入口图标 dx=+340
    )
    with (
        patch.object(test_context.lost_void, 'detect_to_go', return_value=frame),
        patch.object(test_context.controller, 'move_w') as mock_forward,
        patch.object(test_context.controller, 'move_a') as mock_left,
        patch.object(test_context.controller, 'move_d') as mock_right,
    ):
        op._steer_towards_other_interact_icon(exclude_x=None, prefer_entry=True)

    assert mock_forward.called
    assert mock_right.called and not mock_left.called, '应朝入口图标(右侧)横移'


def test_steer_nothing_detected_falls_back(test_context: TestContext) -> None:
    """转向:什么图标都检测不到 → 前进+左右交替兜底。"""
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()

    with (
        patch.object(test_context.lost_void, 'detect_to_go', return_value=_frame_with()),
        patch.object(test_context.controller, 'move_w') as mock_forward,
        patch.object(test_context.controller, 'move_a') as mock_left,
        patch.object(test_context.controller, 'move_d') as mock_right,
    ):
        op.entry_door_block_times = 1
        op._steer_towards_other_interact_icon(exclude_x=None)

    assert mock_forward.called
    assert mock_left.called != mock_right.called, '应按奇偶交替单侧横移'


def test_restart_resets_attempt_timer_and_level_state(test_context: TestContext) -> None:
    """重开挑战成功后:attempt_start_time 重新计时 + 本层交互状态清空。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号', '邦布商店']
    op.interacted_target_key_list = ['感叹号:蕾']
    op.entry_gear_name_list.extend(['[携游]敕令玄幡'])
    op.entry_gear_repeat_times = 2
    op.entry_gear_interact_done = True
    op.entry_door_block_times = 3
    op.ao_fei_li_ya_talked = True
    op.stuck_state.stuck_times = 5

    ok = OperationResult(success=True, status='按钮-退出战斗-确认')
    with patch.object(RestartInBattle, 'execute', return_value=ok):
        result = op.handle_find_target_fail()

    assert result.is_success
    assert result.status == '准备重试'
    assert op.restart_count == 1
    assert op.attempt_start_time > 0, '重开后应重新计时'
    assert op.had_been_list == []
    assert op.interacted_target_key_list == []
    assert op.entry_gear_name_list == []
    assert op.entry_gear_repeat_times == 0
    assert not op.entry_gear_interact_done
    assert op.entry_door_block_times == 0
    assert not op.ao_fei_li_ya_talked
    assert op.stuck_state.stuck_times == 0, '重开后位置已重置 卡住计数也应重新开始'


def _run_try_interact_with_ocr_text(
        test_context: TestContext, op: LostVoidRunLevel, ocr_text: str):
    """驱动 try_interact:交互按键可见 + 交互文本OCR返回指定文本;
    返回(轮次结果, interact mock, move_w mock, move_s mock)。"""
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()
    key_found = op.round_success(status='按键-交互')
    mrl = Mock()
    mrl.max.center.x = 100.0  # 标签在交互文本区域内的相对x(用于换算屏幕x)
    with (
        patch.object(op, 'round_by_find_area', return_value=key_found),
        patch.object(test_context.ocr, 'crop_and_run_ocr', return_value={ocr_text: mrl}),
        patch.object(test_context.lost_void, 'detect_to_go', return_value=Mock(results=[])),
        patch.object(test_context.controller, 'interact') as mock_interact,
        patch.object(test_context.controller, 'move_w') as mock_forward,
        patch.object(test_context.controller, 'move_s') as mock_back,
    ):
        result = op.try_interact()
    return result, mock_interact, mock_forward, mock_back


def test_try_interact_blocked_by_interacted_npc_after_abandon(test_context: TestContext) -> None:
    """放弃感叹号后 交互文本是已交互过的NPC(按下会重复打开武备画面)→ 不按键 走位换目标后重试。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号']
    op.interacted_target_key_list = ['感叹号:蕾']

    result, mock_interact, mock_forward, _ = _run_try_interact_with_ocr_text(test_context, op, '蕾')

    assert result.status == '走位调整交互目标'
    assert not mock_interact.called, '交互文本是已交互NPC时不应按交互键'
    assert mock_forward.called, '应走位换目标'
    assert op.entry_door_block_times == 1


def test_try_interact_blocked_by_interacted_npc_before_abandon(test_context: TestContext) -> None:
    """完成过首次交互后(未放弃感叹号) 交互文本是已交互NPC → 同样不按键 走位换目标。

    2026-08-26 重写:闭环从「只在放弃感叹号后」扩展到「完成首次交互后每次按键前」——
    这是双NPC相邻时第二个NPC选不上的根因防线。
    """
    op = _make_op(test_context)
    op.interacted_target_key_list = ['感叹号:蕾']

    result, mock_interact, mock_forward, _ = _run_try_interact_with_ocr_text(test_context, op, '蕾')

    assert result.status == '走位调整交互目标'
    assert not mock_interact.called, '已交互NPC不应重复按键'
    assert mock_forward.called
    assert op.entry_door_block_times == 1


def test_try_interact_presses_fresh_npc_after_abandon(test_context: TestContext) -> None:
    """放弃感叹号后 交互文本是没交互过的NPC → 按键(补上此前一直没命中的交互)。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号']
    op.interacted_target_key_list = ['感叹号:蕾']

    result, mock_interact, _, _ = _run_try_interact_with_ocr_text(test_context, op, '奥菲莉亚')

    assert result.status == '交互'
    assert mock_interact.called, '未交互过的NPC应正常按键'
    assert op.entry_door_block_times == 0


def test_try_interact_presses_when_text_is_entry(test_context: TestContext) -> None:
    """放弃感叹号后 交互文本是下层入口 → 正常按下交互。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号']
    door_text = LostVoidRegionType.COMBAT_GEAR.value.value

    result, mock_interact, _, _ = _run_try_interact_with_ocr_text(test_context, op, door_text)

    assert result.status == '交互'
    assert mock_interact.called
    assert op.interact_target is not None and op.interact_target.is_entry
    assert op.entry_door_block_times == 0


def test_try_interact_block_limit_interacted_npc_backs_off(test_context: TestContext) -> None:
    """走位重试达上限且标签明确是已交互NPC → 不硬按(必进重复画面) 后退换角度重新接近。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号']
    op.interacted_target_key_list = ['感叹号:蕾']
    op.entry_door_block_times = 8

    result, mock_interact, _, mock_back = _run_try_interact_with_ocr_text(test_context, op, '蕾')

    assert not result.is_success
    assert result.status == '重复交互对象'
    assert not mock_interact.called, '标签明确是已交互NPC时不应硬按'
    assert mock_back.called, '应后退换角度重新接近'
    assert op.entry_door_block_times == 0, '后退重来后走位计数应清零'


def test_try_interact_block_limit_unparsed_presses(test_context: TestContext) -> None:
    """走位重试达上限且标签读不出 → 直接按键兜底(可能是门没读出标签 错按由判重退出自愈)。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号']
    op.interacted_target_key_list = ['感叹号:蕾']
    op.entry_door_block_times = 8

    result, mock_interact, _, _ = _run_try_interact_with_ocr_text(test_context, op, 'NEPS.')

    assert result.status == '交互'
    assert mock_interact.called, '读不出标签时达上限应直接按键兜底'
    assert op.entry_door_block_times == 8


def test_try_interact_first_interaction_not_blocked(test_context: TestContext) -> None:
    """入口层第一次交互(还没交互过任何目标)不受闭环防护影响 正常按键。"""
    op = _make_op(test_context)

    result, mock_interact, _, _ = _run_try_interact_with_ocr_text(test_context, op, '蕾')

    assert result.status == '交互'
    assert mock_interact.called
    assert op.entry_door_block_times == 0


def test_try_interact_unparsed_text_blocked_after_abandon(test_context: TestContext) -> None:
    """放弃感叹号后 交互文本读不出目标(门口常见杂讯)→ 同样不按键 走位后重试。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号']

    result, mock_interact, mock_forward, _ = _run_try_interact_with_ocr_text(test_context, op, 'NEPS.')

    assert result.status == '走位调整交互目标'
    assert not mock_interact.called, '未确认可交互目标时不应盲按'
    assert mock_forward.called
    assert op.entry_door_block_times == 1


def test_try_interact_unparsed_text_presses_before_first_interaction(test_context: TestContext) -> None:
    """第一次交互前 交互文本读不出目标 → 保持官方原行为直接按键。"""
    op = _make_op(test_context)

    result, mock_interact, _, _ = _run_try_interact_with_ocr_text(test_context, op, 'NEPS.')

    assert result.status == '交互'
    assert mock_interact.called
    assert op.entry_door_block_times == 0


def test_after_interact_all_npc_done_ignores_exclamation(test_context: TestContext) -> None:
    """入口层三个NPC(两武备+研究员)都交互完成 → 主动忽略感叹号直接前往下层入口。"""
    for gear_names, interacted, expect_ignore in [
        (['[携游]敕令玄幡', '[照]月魄凛光'], ['感叹号:蕾', '感叹号:神出鬼没的研究员'], True),
        (['[携游]敕令玄幡'], ['感叹号:蕾', '感叹号:神出鬼没的研究员'], False),  # 只选到一个武备
        (['[携游]敕令玄幡', '[照]月魄凛光'], ['感叹号:蕾'], False),  # 研究员还没交互
    ]:
        op = _make_op(test_context)
        test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
        op.screenshot()
        op.entry_gear_name_list.extend(gear_names)
        op.interacted_target_key_list = list(interacted)
        op.locked_interact_target = LostVoidInteractTarget(name='奥菲莉亚', icon='感叹号', is_npc=True)
        op.interact_target = op.locked_interact_target

        with (
            patch.object(test_context.lost_void, 'in_normal_world', return_value=True),
            patch.object(op, 'move_after_interact'),
        ):
            result = op.after_interact()

        case = f'{gear_names}/{interacted}'
        assert result.is_success, case
        assert ('感叹号' in op.had_been_list) == expect_ignore, case


def test_handle_find_target_fail_abandons_exclamation_first(test_context: TestContext) -> None:
    """入口层完成过武备选择后的超时 → 先放弃感叹号找下层入口(不重开 不消耗重试次数);
    已放弃过 / 没选到武备 / 非入口层 → 正常重开。"""
    for region, gear_names, had_been, expect_abandon in [
        (LostVoidRegionType.ENTRY, ['[携游]敕令玄幡'], [], True),
        (LostVoidRegionType.ENTRY, ['[携游]敕令玄幡'], ['感叹号'], False),
        (LostVoidRegionType.ENTRY, [], [], False),
        (LostVoidRegionType.COMBAT_GEAR, ['[携游]敕令玄幡'], [], False),
    ]:
        op = _make_op(test_context, region)
        op.entry_gear_name_list.extend(gear_names)
        op.had_been_list = list(had_been)

        ok = OperationResult(success=True, status='按钮-退出战斗-确认')
        with patch.object(RestartInBattle, 'execute', return_value=ok) as mock_restart:
            result = op.handle_find_target_fail()

        case = f'{region}/{gear_names}/{had_been}'
        assert result.is_success and result.status == '准备重试', case
        if expect_abandon:
            assert not mock_restart.called, f'{case}: 应放弃感叹号而不是重开'
            assert '感叹号' in op.had_been_list, case
            assert op.restart_count == 0, f'{case}: 不应消耗重开次数'
            assert op.attempt_start_time > 0, f'{case}: 应重置计时起点'
        else:
            assert mock_restart.called, f'{case}: 应正常重开'
            assert op.restart_count == 1, case


def test_approach_after_abandon_keeps_moving_forward(test_context: TestContext) -> None:
    """放弃感叹号后的站位调整:不后退 不查剩余感叹号 保持前进。"""
    op = _make_op(test_context)
    op.had_been_list = ['感叹号']
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()

    mock_detector = Mock()
    with (
        patch.object(test_context.lost_void, 'detector', mock_detector),
        patch.object(test_context.controller, 'move_s') as mock_back,
        patch.object(test_context.controller, 'move_w') as mock_forward,
    ):
        op._approach_remaining_interact_target()

    assert mock_forward.called, '应保持前进'
    assert not mock_back.called, '不应后退(会退回被抢交互的位置)'
    assert not mock_detector.get_result_by_x.called, '放弃后不需要再找剩余感叹号'


def test_non_battle_check_timeout_by_attempt_start_time(test_context: TestContext) -> None:
    """超时起点:attempt_start_time 为0时用 operation_start_time(旧行为);
    重开后 attempt_start_time 是新时间 → 不会立刻超时。"""
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')

    # 情况1: 未重开过(attempt_start_time=0) 指令开始时间已超10分钟 → 超时
    op = _make_op(test_context)
    op.screenshot()
    op.operation_start_time = time.time() - 700
    with patch.object(test_context.lost_void, 'in_normal_world', return_value=True):
        result = op.non_battle_check()
    assert not result.is_success
    assert result.status == '执行超时'

    # 情况2: 重开后(attempt_start_time=刚刚) 即使指令开始时间已超10分钟 → 不超时
    op = _make_op(test_context)
    test_context.mock_screen('迷失之地-大世界', '玛琳前-以太稳定')
    op.screenshot()
    op.operation_start_time = time.time() - 700
    op.attempt_start_time = time.time()
    test_context.lost_void.priority_updated = True
    mock_detector = Mock()
    mock_detector.is_frame_with_all.return_value = (False, False, False)
    with (
        patch.object(test_context.lost_void, 'in_normal_world', return_value=True),
        patch.object(test_context.lost_void, 'detect_to_go', return_value=Mock()),
        patch.object(test_context.lost_void, 'detector', mock_detector),
        patch.object(test_context.lost_void, 'check_battle_encounter', return_value=False),
        patch.object(test_context.lost_void, 'check_battle_encounter_in_period', return_value=False),
        patch.object(test_context.controller, 'turn_by_distance'),
    ):
        result = op.non_battle_check()
    assert result.status != '执行超时', '重开后不应立刻超时'
