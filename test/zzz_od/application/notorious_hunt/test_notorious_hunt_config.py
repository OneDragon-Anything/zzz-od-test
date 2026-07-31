"""``NotoriousHuntConfig`` 计划迭代状态机的纯单测(不读 yml、不写盘、不依赖画面)。

与 ``ChargePlanConfig`` 同构(共用 ``ChargePlanItem``),构造同样用 ``__new__`` 绕过 ``__init__``、
注入 ``plan_list`` + mock ``save``。差异已在用例里体现:

- ``reset_plans``:notorious_hunt 用 ``modified`` 标志、**循环外 save 一次**(charge_plan 循环内每轮 save)。
- ``all_plan_finished``:无 ``plan_list is None`` 守卫(不给 None 用例)。
- ``_is_same_plan``:无 ``compare_plan_id`` 参数,fallback 是 4 字段(tab/category/mission_type/mission_name)比较。
- 无 ``try_reset_plan_times_by_dt``(恶名狩猎无每日重置)。

``reset_plans`` 的空守卫同样用来锁住 SR ``check_plan`` 空计划死循环 bug 的等价防线。
"""

from unittest.mock import MagicMock

from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig


def _make_config(
    plans: list[ChargePlanItem] | None = None,
) -> NotoriousHuntConfig:
    """造一个不触盘的 ``NotoriousHuntConfig``:``__new__`` 绕过 ``__init__``,注入 plan_list + mock save。"""
    config = NotoriousHuntConfig.__new__(NotoriousHuntConfig)
    config.data = {}
    config.plan_list = plans if plans is not None else []
    config.save = MagicMock()  # 记录调用、不写盘
    return config


def _plan(
    run_times: int = 0,
    plan_times: int = 1,
    *,
    plan_id: str | None = None,
    skipped: bool = False,
    name: str = '调查专项',
) -> ChargePlanItem:
    """造一个 ``ChargePlanItem``;``plan_id`` 给定则用给定值,否则由 ``__post_init__`` 自动生成。"""
    return ChargePlanItem(
        mission_name=name,
        run_times=run_times,
        plan_times=plan_times,
        plan_id=plan_id,
        skipped=skipped,
    )


# ---------- reset_plans ----------


def test_reset_plans_empty_plan_list_is_noop() -> None:
    """空 plan_list:早返,不扣减、不 save(锁住空守卫,防 SR 空计划死循环回归)。"""
    config = _make_config(plans=[])
    config.reset_plans()
    config.save.assert_not_called()


def test_reset_plans_all_zero_plan_times_is_noop() -> None:
    """全部 plan_times==0:eligible 为空 → 早返,不扣减、不 save。"""
    config = _make_config(plans=[_plan(run_times=2, plan_times=0, plan_id='a')])
    config.reset_plans()
    assert config.plan_list[0].run_times == 2
    config.save.assert_not_called()


def test_reset_plans_all_skipped_is_noop() -> None:
    """全部 skipped:eligible 为空 → 早返,不扣减、不 save。"""
    config = _make_config(plans=[_plan(run_times=2, skipped=True, plan_id='a')])
    config.reset_plans()
    assert config.plan_list[0].run_times == 2
    config.save.assert_not_called()


def test_reset_plans_with_incomplete_does_nothing() -> None:
    """有任一未完成项 → break,modified 保持 False,不扣减、不 save。"""
    config = _make_config(plans=[
        _plan(run_times=0, plan_times=1, plan_id='a'),
        _plan(run_times=2, plan_times=1, plan_id='b'),
    ])
    config.reset_plans()
    assert config.plan_list[0].run_times == 0
    assert config.plan_list[1].run_times == 2
    config.save.assert_not_called()


def test_reset_plans_all_complete_equal_subtracts_to_zero() -> None:
    """全部完成且相等 → 逐轮扣到 0;modified=True → 循环外 save 一次(区别于 charge_plan 每轮 save)。"""
    config = _make_config(plans=[
        _plan(run_times=2, plan_times=1, plan_id='a'),
        _plan(run_times=2, plan_times=1, plan_id='b'),
    ])
    config.reset_plans()
    assert [p.run_times for p in config.plan_list] == [0, 0]
    assert config.save.call_count == 1


def test_reset_plans_mixed_subtracts_until_min_below_plan_times() -> None:
    """混合:逐轮全员扣减,直到最少那个 < plan_times 才停(A=3,B=1 → A=2,B=0)。"""
    config = _make_config(plans=[
        _plan(run_times=3, plan_times=1, plan_id='a'),
        _plan(run_times=1, plan_times=1, plan_id='b'),
    ])
    config.reset_plans()
    assert [p.run_times for p in config.plan_list] == [2, 0]


def test_reset_plans_skipped_not_subtracted() -> None:
    """skipped 项不进 eligible,不被扣减;只扣 eligible 的(B 从 2→0,A 保持 5)。"""
    config = _make_config(plans=[
        _plan(run_times=5, plan_times=1, skipped=True, plan_id='a'),
        _plan(run_times=2, plan_times=1, plan_id='b'),
    ])
    config.reset_plans()
    assert config.plan_list[0].run_times == 5  # skipped 原样
    assert config.plan_list[1].run_times == 0


# ---------- get_next_plan ----------


def test_get_next_plan_empty_returns_none() -> None:
    """空 plan_list → None。"""
    config = _make_config(plans=[])
    assert config.get_next_plan() is None


def test_get_next_plan_no_last_tried_returns_first_incomplete() -> None:
    """无 last_tried → 从头找第一个未完成。"""
    config = _make_config(plans=[
        _plan(run_times=1, plan_times=1, plan_id='a'),  # 已完成
        _plan(run_times=0, plan_times=1, plan_id='b'),  # 未完成
    ])
    result = config.get_next_plan()
    assert result is config.plan_list[1]


def test_get_next_plan_after_last_tried_returns_next_incomplete() -> None:
    """last_tried 在列表中 → 从其后找下一个未完成。"""
    config = _make_config(plans=[
        _plan(run_times=0, plan_times=1, plan_id='a'),
        _plan(run_times=0, plan_times=1, plan_id='b'),
    ])
    result = config.get_next_plan(last_tried_plan=_plan(run_times=0, plan_times=1, plan_id='a'))
    assert result is config.plan_list[1]


def test_get_next_plan_last_tried_is_last_item_returns_none_no_wrap() -> None:
    """last_tried 是最后一项 → 越界返回 None,不回卷到开头。"""
    config = _make_config(plans=[
        _plan(run_times=0, plan_times=1, plan_id='a'),
        _plan(run_times=0, plan_times=1, plan_id='b'),
    ])
    result = config.get_next_plan(last_tried_plan=_plan(run_times=0, plan_times=1, plan_id='b'))
    assert result is None


def test_get_next_plan_last_tried_not_in_list_starts_from_head() -> None:
    """last_tried 不在列表 → 失配,start_index 保持 0,从头找。"""
    config = _make_config(plans=[
        _plan(run_times=0, plan_times=1, plan_id='a'),
        _plan(run_times=0, plan_times=1, plan_id='b'),
    ])
    result = config.get_next_plan(last_tried_plan=_plan(run_times=0, plan_times=1, plan_id='zzz'))
    assert result is config.plan_list[0]


def test_get_next_plan_skips_skipped_plans() -> None:
    """skipped 项被跳过,返回其后的未完成项。"""
    config = _make_config(plans=[
        _plan(run_times=0, plan_times=1, skipped=True, plan_id='a'),
        _plan(run_times=0, plan_times=1, plan_id='b'),
    ])
    result = config.get_next_plan()
    assert result is config.plan_list[1]


def test_get_next_plan_all_complete_returns_none() -> None:
    """全部完成 → None。"""
    config = _make_config(plans=[_plan(run_times=1, plan_times=1, plan_id='a')])
    assert config.get_next_plan() is None


# ---------- all_plan_finished ----------


def test_all_plan_finished_empty_is_true() -> None:
    """空 plan_list → True(无可完成项)。"""
    config = _make_config(plans=[])
    assert config.all_plan_finished() is True


def test_all_plan_finished_all_complete_is_true() -> None:
    """非 skipped 全部 run>=plan → True。"""
    config = _make_config(plans=[_plan(run_times=2, plan_times=2, plan_id='a')])
    assert config.all_plan_finished() is True


def test_all_plan_finished_some_incomplete_is_false() -> None:
    """任一非 skipped 未完成 → False。"""
    config = _make_config(plans=[_plan(run_times=0, plan_times=1, plan_id='a')])
    assert config.all_plan_finished() is False


def test_all_plan_finished_ignores_skipped() -> None:
    """skipped 项不参与判定:skipped 未完成 + 其余完成 → True。"""
    config = _make_config(plans=[
        _plan(run_times=0, plan_times=1, skipped=True, plan_id='a'),
        _plan(run_times=1, plan_times=1, plan_id='b'),
    ])
    assert config.all_plan_finished() is True


# ---------- add_plan_run_times ----------


def test_add_plan_run_times_increments_first_incomplete_match() -> None:
    """to_add 匹配到未完成项 → +1 该项并 save。"""
    config = _make_config(plans=[_plan(run_times=0, plan_times=2, plan_id='a')])
    config.add_plan_run_times(_plan(run_times=0, plan_times=2, plan_id='a'))
    assert config.plan_list[0].run_times == 1
    config.save.assert_called_once()


def test_add_plan_run_times_falls_back_to_any_match_when_all_complete() -> None:
    """to_add 只匹配到已完成项 → 第二轮兜底:仍 +1 该匹配项。"""
    config = _make_config(plans=[_plan(run_times=2, plan_times=2, plan_id='a')])
    config.add_plan_run_times(_plan(run_times=2, plan_times=2, plan_id='a'))
    assert config.plan_list[0].run_times == 3
    config.save.assert_called_once()


def test_add_plan_run_times_no_match_is_noop() -> None:
    """to_add 无匹配项 → 不动、不 save。"""
    config = _make_config(plans=[_plan(run_times=0, plan_times=1, plan_id='a')])
    config.add_plan_run_times(_plan(run_times=0, plan_times=1, plan_id='zzz'))
    assert config.plan_list[0].run_times == 0
    config.save.assert_not_called()


# ---------- _is_same_plan ----------


def test_is_same_plan_by_plan_id_same_is_true() -> None:
    """双方都有 plan_id 且相同 → True。"""
    config = _make_config()
    a = _plan(plan_id='x')
    b = _plan(plan_id='x', run_times=5)
    assert config._is_same_plan(a, b) is True


def test_is_same_plan_by_plan_id_diff_is_false() -> None:
    """plan_id 不同 → False。"""
    config = _make_config()
    a = _plan(plan_id='x')
    b = _plan(plan_id='y')
    assert config._is_same_plan(a, b) is False


def test_is_same_plan_fallback_same_fields_is_true() -> None:
    """缺 plan_id(空串)时回退 4 字段比较,4 字段全同 → True(旧数据兼容)。"""
    config = _make_config()
    a = _plan(plan_id='')
    b = _plan(plan_id='', run_times=5)
    assert config._is_same_plan(a, b) is True


def test_is_same_plan_fallback_diff_fields_is_false() -> None:
    """缺 plan_id 时回退 4 字段比较,mission_name 不同 → False。"""
    config = _make_config()
    a = _plan(plan_id='', name='调查专项')
    b = _plan(plan_id='', name='其它专项')
    assert config._is_same_plan(a, b) is False


def test_is_same_plan_none_operand_is_false() -> None:
    """任一操作数为 None → False。"""
    config = _make_config()
    a = _plan(plan_id='x')
    assert config._is_same_plan(a, None) is False
    assert config._is_same_plan(None, a) is False
