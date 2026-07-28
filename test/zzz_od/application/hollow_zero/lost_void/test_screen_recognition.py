"""迷失之地画面识别测试 —— 覆盖运行逻辑中 bot 需识别的全部画面。

TDD 思路:每个画面一个参数化用例(load 中央存档 fixture → assert get_match_screen_name)。
- **缺 fixture** 的用例 error(load_screen 断言文件存在)→ 这些就是要采集的截图。
- **有 fixture 但识别不出 / 识别错** → 该 fixture 是过渡帧 / 质量差 → 也要重采。

跑这个测试 → 失败/报错的画面集 = 待采集(或重采)清单。
"""
import pytest

from test.conftest import TestContext

from one_dragon.base.screen import screen_utils

# (画面, fixture state)。state 缺的 / 识别不过的 → 采集清单。
SCREENS: list[tuple[str, str]] = [
    # 已有 central fixture(验证识别 OK):
    ('迷失之地-大世界', '玛琳前-以太稳定'),
    ('迷失之地-通用选择', '选1张卡牌'),
    ('迷失之地-武备选择', '初始战术棱镜方案'),
    ('迷失之地-挑战结果', '奖励展示态'),
    ('迷失之地-路径迭换', '选定位卡'),
    ('迷失之地-抽奖机', '抽奖前'),
    # 缺 central fixture(待采集):
    ('迷失之地-邦布商店', '商店'),
    # ('迷失之地-入口', '枢纽'),  # skip:入口枢纽 id_mark 全 false,与入口-周期/常规共享 area 混淆,不独立建档
    ('迷失之地-入口-周期', '周期副本'),
    ('迷失之地-入口-常规', '常规副本'),
    ('迷失之地-战线肃清', '选战略'),
    ('迷失之地-矩阵行动', '编队选择'),
    ('迷失之地-矩阵行动-编队选择', '编队'),
    ('迷失之地-特遣调查', '特遣任务'),
    ('迷失之地-战斗失败', '撤退'),
]


@pytest.mark.parametrize('screen_name, state', SCREENS,
                         ids=[f'{s}' for s, _ in SCREENS])
def test_recognize(test_context: TestContext, screen_name: str, state: str) -> None:
    img = test_context.load_screen(screen_name, state)
    result = screen_utils.get_match_screen_name(test_context, img)
    assert result == screen_name, f'{screen_name}/{state}: 识别为 {result}'
