"""自动战斗配置"非战斗兜底"回归守卫。

针对「全配队通用」(所有配队的默认回退模板,auto_battle_operator.FALLBACK_TEMPLATE_NAME),
检查其中是否存在「未被战内信号守住」的兜底操作 —— 即战斗结束后(战内状态失配、
流程落到兜底分支)仍会触发的操作。这类操作若是攻击类(普攻 / 特殊技 / 终结技等),
会在结算页误触与该键共用的按钮(#2157:普攻 X 与"再来一次"共用 X)。

战内信号(剪枝集):祖先 states(含 scene 的 triggers)含【正向,非 `!` 否定】的
这些前缀 → 视为"在战斗画面才为真"→ 该 operation 不会战后触发 → 安全:
  - `[前台-/后台-/后台-1-/后台-2-…]`:前台/后台任意状态(角色 / 能量 / 血量扣减 / 类型 等),
    3 人队识别到任意位置的任意战内 UI = 在战斗画面
  - `[按键可用-…]`:任意按钮可用(终结技/特殊攻击/快速支援/切换后援/普通攻击/连携技 等)
  - `[连携技-…]`:连携技画面状态;`[闪避识别-…]`:闪避识别(黄光等)
  - `[自定义-…]`:战内自定义事件(连携跳过/失衡时间/黄光切人/快速支援换人 等,战中才设)
  - `[<角色>-…]`:角色专属状态(如 `[苍角-能量]`)
  - scene 的 `triggers`:scene 只在 trigger 触发时活跃,trigger 是上面任一战内信号时,
    整个 scene 的 handler 都受其约束(作顶层祖先参与剪枝)

加载用 `AutoBattleOperator.init()`(走真实 loader,展开所有 state_template /
operation_template),再遍历展开后的 Scene → StateHandler 树,收集每个叶子 operation
的祖先 states 链。比手写递归复刻 loader 更可靠(展开逻辑直接复用框架)。
"""
from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from test.conftest import TestContext

from one_dragon.base.conditional_operation.state_handler import StateHandler
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator

# 受检入口配置:全配队通用(默认回退模板,覆盖面最广)
_ENTRY = '全配队通用'

# 前台/后台任意位置的任意状态(角色 / 能量 / 血量扣减 / 类型 等)→ 在战斗画面
_POSITIONS = ['前台-', '后台-', '后台-1-', '后台-2-']
# 速切模板里非角色(通用)模板,不算角色名
_NON_CHAR_TEMPLATES = {'速切模板-全角色', '速切模板-通用', '速切模板-强攻站场'}
# 战内信号前缀:祖先 states 含这些前缀的【正向】状态 → 在战斗画面为真
#   按键可用-  :任意按钮可用(终结技/特殊攻击/快速支援/切换后援/普通攻击/连携技 等)
#   连携技-    :连携技画面(连携技-1-<角色> / 连携技-2-<角色> / 连携技-准备)
#   闪避识别-  :闪避识别(黄光等)
#   自定义-    :战内自定义事件(连携跳过/失衡时间/黄光切人/快速支援换人/锁定丢失 等,
#               均由 auto_op 在战斗中"设置状态"写入,非战斗不发生)
_IN_BATTLE_STATE_PREFIXES = ['按键可用-', '连携技-', '闪避识别-', '自定义-']

_STATE_HANDLER_DIR = Path('config') / 'auto_battle_state_handler'


def _agent_names() -> list[str]:
    """从 `速切模板-*.sample.yml` 文件名推导角色名(排除非角色通用模板)。"""
    names: list[str] = []
    for p in _STATE_HANDLER_DIR.glob('速切模板-*.sample.yml'):
        name = p.name.replace('速切模板-', '').replace('.sample.yml', '')
        if name not in _NON_CHAR_TEMPLATES:
            names.append(name)
    return names


def _prune_members() -> tuple[list[str], list[str]]:
    """返回 (精确剪枝成员, 前缀剪枝成员),合起来代表"在战斗画面才为真"的战内信号。

    祖先 states(含 scene triggers)含【正向,非 !】的任一即视为战内安全。
    全部用前缀匹配:前台/后台任意状态、角色专属、各类战内信号前缀。
    """
    names = _agent_names()
    exact: list[str] = []
    prefix = (
        _POSITIONS  # 前台-/后台-…:任意位置任意状态(角色/能量/血量扣减/类型…)= 在战斗画面
        + [f'{n}-' for n in names]  # [角色-…]:角色专属状态(如 [苍角-能量])
        + _IN_BATTLE_STATE_PREFIXES  # 按键可用-/连携技-/闪避识别-/自定义-
    )
    return exact, prefix


def _is_pruned(ancestor_states: list[str], exact: list[str], prefix: list[str]) -> bool:
    """任一祖先 states 含【正向(未 `!` 否定)】剪枝成员 → 视为战内安全。"""
    for s in ancestor_states:
        if not s:
            continue
        for m in exact:
            # [成员] 或 [成员, …],且前方无 ! 否定
            if re.search(rf'(?<!!)\[{re.escape(m)}(?=[\],])', s):
                return True
        for m in prefix:
            if re.search(rf'(?<!!)\[{re.escape(m)}', s):
                return True
    return False


def _walk(handler: StateHandler, ancestor_states: list[str], results: list[dict]) -> None:
    """递归遍历展开后的 StateHandler 树,收集叶子 operation + 祖先 states 链。"""
    states: str = handler.states
    sub_handlers = handler.sub_handlers
    operations = handler.operations
    if sub_handlers:
        anc = ancestor_states + [states]
        for sub in sub_handlers:
            _walk(sub, anc, results)
    elif operations:
        anc = ancestor_states + [states]
        for op_def in operations:
            results.append({
                'op_name': op_def.op_name or '',
                'ancestor_states': anc,
                'parent_states': states,
            })


def _collect_ungated(
    test_context: TestContext,
    op_filter: Callable[[str], bool],
) -> list[dict]:
    """加载全配队通用,返回「未 gated(非战内)的兜底 operation」列表。

    Args:
        test_context: 测试 fixture(提供 auto_battle_context)
        op_filter: 操作名过滤(如只看普攻,或看全部)

    Returns:
        未被战内信号守住的兜底 operation 列表,每项含 op_name / parent_states / ancestor_states
    """
    op = AutoBattleOperator(test_context.auto_battle_context, 'auto_battle', _ENTRY)
    op.init()
    exact, prefix = _prune_members()
    all_ops: list[dict] = []
    for scene in op.scenes:
        # scene 的 triggers 也是战内信号来源:scene 只在这些状态触发时才活跃,
        # trigger 若是战内(如 按键可用-X)则整个 scene 的 handler 都受其约束。
        # 包成 [trigger] 放进祖先链,让剪枝正则按战内信号匹配。
        triggers = [f'[{t}]' for t in scene.triggers]
        for handler in scene.handlers:
            _walk(handler, triggers, all_ops)
    return [
        r for r in all_ops
        if op_filter(r['op_name']) and not _is_pruned(r['ancestor_states'], exact, prefix)
    ]


class TestAutoBattleFallbackGuard:

    def test_no_ungated_normal_attack_fallback(self, test_context: TestContext) -> None:
        """普攻兜底必须被战内信号守住:未 gated 的普攻兜底应为 0(否则战后残留普攻,#2157)。"""

        def is_normal_attack(op_name: str) -> bool:
            return '普通攻击' in op_name and not op_name.endswith('松开')

        candidates = _collect_ungated(test_context, is_normal_attack)
        assert candidates == [], (
            '存在未被战内信号守住的普攻兜底(战后会残留发普攻,#2157):\n'
            + '\n'.join(
                f"  op={c['op_name']!r} parent_states={c['parent_states']!r}" for c in candidates
            )
        )

    def test_no_ungated_fallback_in_combat(self, test_context: TestContext) -> None:
        """所有兜底操作(不限普攻)都必须被战内信号守住:未 gated 兜底应为 0。

        比 test_no_ungated_normal_attack_fallback 更严格,覆盖按键-连携技 / 终结技 /
        特殊攻击 / 切换后援等所有操作类型 —— 任何战后会触发的兜底都可能误触结算页
        按钮(#2157 类)。当前剪枝集(战内信号前缀 + scene triggers)已覆盖全部战内
        信号,全配队通用里所有兜底都被某个战内信号守住,故应为 0。
        """
        candidates = _collect_ungated(test_context, lambda _: True)
        assert candidates == [], (
            '存在未被战内信号守住的兜底操作(战后会触发):\n'
            + '\n'.join(
                f"  op={c['op_name']!r} ancestors={c['ancestor_states']}" for c in candidates
            )
        )
