"""LostVoidChooseCommon.check_choose_title 标题识别分支测试。

按 testing methodology 动作一:check_choose_title 按「区域-标题」OCR 命中不同标题 → 设不同
子态标志(to_choose_artifact / to_choose_gear / to_choose_gear_branch / to_choose_num)。
每个标题规则一个用例(mock 对应 fixture → 调 check_choose_title → 断言标志)。

覆盖 check_choose_title 全部 8 条 exact rule(读 ``lost_void_choose_common.py`` L466+ 确认):
- CHOOSE_1_CARD(选1张卡牌)/ CHOOSE_2(选2项)/ CHOOSE_1_GEAR(选1武备)/
  GEAR_BRANCH(战术棱镜分支)/ ARTIFACT_GAIN(获得战利品)/ GEAR_GAIN(获得武备)/
  GEAR_UPGRADE(武备已升级)/ CHOOSE_1(选1枚鸣徽,1.5 后仅设 num=1)。

缺 fixture 的标题分支会 error(mock_screen 断言文件存在)→ 这些就是要补采的 通用选择 子态,
run 采到后补 fixture → 用例转 GREEN(TDD 圈定,保留不删)。
"""
import pytest
from test.conftest import TestContext

from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import (
    LostVoidChooseCommon,
)


def _setup_op(test_context: TestContext) -> LostVoidChooseCommon:
    test_context.lost_void.load_artifact_data()
    test_context.lost_void.load_challenge_config()
    return LostVoidChooseCommon(test_context)


# (fixture state, 期望 to_choose_artifact, to_choose_gear, to_choose_gear_branch, to_choose_num)
# 现有 fixture: 选1张卡牌(CHOOSE_1_CARD)。其余标题分支的 fixture 待采 → 用例 RED 圈定。
# 期望值对照 check_choose_title 各 rule 的 apply_rule 分支(L485-507):
# - GEAR_GAIN / GEAR_UPGRADE:to_choose_gear=True, num=0
# - ARTIFACT_GAIN:to_choose_artifact=True, num=0
# - GEAR_BRANCH:to_choose_gear=True, to_choose_gear_branch=True, num=1
# - CHOOSE_2:to_choose_artifact=True, num=2
# - CHOOSE_1_GEAR:to_choose_gear=True, num=1
# - CHOOSE_1_CARD:to_choose_artifact=True, num=1
# - CHOOSE_1:仅 to_choose_num=1(1.5 后武备和鸣徽都可能是此标题,不设 artifact/gear)
TITLE_CASES = [
    ('选1张卡牌', True, False, False, 1),     # CHOOSE_1_CARD(已有 fixture → GREEN)
    # 以下待采 fixture(TDD 圈定,fixture 采集后转 GREEN):
    ('选2项', True, False, False, 2),           # CHOOSE_2
    ('选1武备', False, True, False, 1),          # CHOOSE_1_GEAR
    ('战术棱镜分支', False, True, True, 1),       # GEAR_BRANCH
    ('获得战利品', True, False, False, 0),        # ARTIFACT_GAIN(无需选)
    ('获得武备', False, True, False, 0),          # GEAR_GAIN(无需选)
    ('武备已升级', False, True, False, 0),         # GEAR_UPGRADE(无需选)
    ('选1枚鸣徽', False, False, False, 1),        # CHOOSE_1(1.5 后仅 num=1,不设 artifact/gear)
]


@pytest.mark.parametrize('state, artifact, gear, branch, num', TITLE_CASES,
                         ids=[c[0] for c in TITLE_CASES])
def test_check_choose_title(test_context: TestContext, state: str,
                            artifact: bool, gear: bool, branch: bool, num: int) -> None:
    op = _setup_op(test_context)
    test_context.mock_screen('迷失之地-通用选择', state)
    op.screenshot()
    op.check_choose_title(op.last_screenshot)
    assert op.to_choose_artifact is artifact, f'{state}: to_choose_artifact'
    assert op.to_choose_gear is gear, f'{state}: to_choose_gear'
    assert op.to_choose_gear_branch is branch, f'{state}: to_choose_gear_branch'
    assert op.to_choose_num == num, f'{state}: to_choose_num'
