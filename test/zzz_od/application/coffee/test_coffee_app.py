"""CoffeeApp 选咖啡测试。

对话点单(PR #2574 POINT_3 片刻闲) ``dialog_choose_coffee`` 的选项态分支:
- 识别 ``对话框标题-汀曼大师`` + 在 ``右侧选项区域`` OCR 点击候选咖啡
- POINT_3(片刻闲)点单后返回 ``点单后跳过``;POINT_2(汀曼咖啡)返回 ``已点单``
- 候选顺序:额外咖啡 → 汀曼特调 → 浓缩咖啡(保底,没有汀曼特调的账号用)

咖啡列表(POINT_1 六分街) ``choose_coffee`` 的分支(OCR 结果用假数据,测选择逻辑和点击位置):
- 有汀曼特调 → 选汀曼特调
- 重试到最后一次仍没有汀曼特调 → 改选浓缩咖啡(issue #3055)
- 前几轮没认出汀曼特调(列表可能还在滑入) → 先重试,不点浓缩咖啡
- 汀曼特调 OCR 不准(只在低阈值命中) → 仍选汀曼特调,不被高阈值命中的浓缩咖啡抢先
- 汀曼特调和浓缩咖啡都没有 / 浓缩咖啡已喝过 → ``没找到目标咖啡``

fixture(`screens/咖啡店/对话点单-选项.webp`):POINT_3 片刻闲 未喝过选项态
(汀曼大师对话框 + 右侧「来杯「汀曼特调」/ 来杯『鲜萃红茶』/ 不喝了」)。
"""
import numpy as np
import pytest
from test.conftest import TestContext

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.coffee.coffee_app import CoffeeApp
from zzz_od.application.coffee.coffee_config import CoffeeTransportPoint


def _fake_ocr_map(words: list[str]) -> dict[str, MatchResultList]:
    """把咖啡名列表做成 run_ocr 的返回格式，每个名字横向排开"""
    ocr_map: dict[str, MatchResultList] = {}
    for idx, word in enumerate(words):
        mrl = MatchResultList()
        mrl.append(MatchResult(1, 100 + idx * 200, 300, 150, 30, data=word))
        ocr_map[word] = mrl
    return ocr_map


class TestCoffeeApp:
    """咖啡店 app 选咖啡测试。"""

    def _make_op(self, test_context: TestContext) -> CoffeeApp:
        """mock 选项态截图 + 建 CoffeeApp。"""
        test_context.mock_screen('咖啡店', '对话点单-选项')
        op = CoffeeApp(test_context)
        op.screenshot()
        return op

    def _expected_day_coffee(self) -> str:
        """额外咖啡之外固定选汀曼特调(#2486 起不再按星期选择)。"""
        return '汀曼特调'

    def test_dialog_choose_coffee_point3(self, test_context: TestContext) -> None:
        """POINT_3 选项态 → OCR 点候选咖啡 → 返回「点单后跳过」。"""
        op = self._make_op(test_context)
        op.config.transport_point = CoffeeTransportPoint.POINT_3.value.value
        result = op.dialog_choose_coffee()
        assert result.is_success, '选项态应识别候选咖啡并点击'
        assert result.status == '点单后跳过', f'POINT_3 点单后应返回「点单后跳过」,实际 {result.status}'
        assert op.chosen_coffee.coffee_name == self._expected_day_coffee(), \
            f'应选择 {self._expected_day_coffee()},实际 {op.chosen_coffee.coffee_name if op.chosen_coffee else None}'

    def test_dialog_choose_coffee_point2(self, test_context: TestContext) -> None:
        """POINT_2 选项态 → OCR 点候选咖啡 → 返回「已点单」(回归)。"""
        op = self._make_op(test_context)
        op.config.transport_point = CoffeeTransportPoint.POINT_2.value.value
        result = op.dialog_choose_coffee()
        assert result.is_success, '选项态应识别候选咖啡并点击'
        assert result.status == '已点单', f'POINT_2 点单后应返回「已点单」,实际 {result.status}'
        assert op.chosen_coffee.coffee_name == self._expected_day_coffee(), \
            f'应选择 {self._expected_day_coffee()},实际 {op.chosen_coffee.coffee_name if op.chosen_coffee else None}'

    def test_dialog_choose_coffee_fallback_last(self, test_context: TestContext,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
        """对话点单按优先级点击：浓缩咖啡排在汀曼特调之后，只有前面的都没出现才会点它。"""
        op = self._make_op(test_context)
        captured: list[list[str]] = []

        def fake_click(target_cn_list: list[str], **kwargs: object) -> OperationRoundResult:
            captured.append(list(target_cn_list))
            return op.round_retry('未匹配到目标文本')

        monkeypatch.setattr(op, 'round_by_ocr_and_click_by_priority', fake_click)
        op.dialog_choose_coffee()
        assert captured, '应按优先级 OCR 点击候选咖啡'
        targets = captured[0]
        assert targets[-2:] == ['汀曼特调', '浓缩咖啡'], \
            f'候选末尾应是 汀曼特调 → 浓缩咖啡,实际 {targets}'

    def _choose_from_list(self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch,
                          words: list[str], had_coffee: set[str] | None = None,
                          last_round: bool = True) -> tuple[CoffeeApp, OperationRoundResult, list[Point]]:
        """
        用假的 OCR 结果跑「选择咖啡」节点（POINT_1 咖啡列表）
        :param words: 咖啡列表里 OCR 出来的文字
        :param had_coffee: 额外已喝过的咖啡；额外咖啡默认都视为喝过，只测汀曼特调和保底的选择
        :param last_round: 是否是这个节点的最后一次重试（保底咖啡只在最后一次才找）
        :return: (app, 节点返回, 点击过的坐标)
        """
        op = CoffeeApp(test_context)
        test_context.add_mock_screenshot(np.zeros((1080, 1920, 3), dtype=np.uint8))
        op.screenshot()
        op.had_coffee_list = {c.coffee_name for c in test_context.compendium_service.get_extra_coffee_list()}
        op.had_coffee_list |= had_coffee or set()
        # 直接调节点时重试次数用的是 app 的默认值，这里按「选择咖啡」节点的实际设置（3 次重试）模拟第几轮
        op.node_max_retry_times = 3
        op.node_retry_times = op.node_max_retry_times if last_round else 0
        clicked: list[Point] = []
        monkeypatch.setattr(test_context.controller, 'click',
                            lambda pos=None, *args, **kwargs: clicked.append(pos) or True)
        monkeypatch.setattr(test_context.ocr, 'run_ocr', lambda image, *args, **kwargs: _fake_ocr_map(words))
        return op, op.choose_coffee(), clicked

    def _expected_click_x(self, test_context: TestContext, words: list[str], word: str) -> int:
        """假 OCR 里某个咖啡名被点击时的 x 坐标（文字中心 + 咖啡列表区域左上角）"""
        area = test_context.screen_loader.get_area('咖啡店', '咖啡列表')
        return _fake_ocr_map(words)[word].max.center.x + area.left_top.x

    def test_choose_coffee_tinman(self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """列表里有汀曼特调 → 选汀曼特调，点的是汀曼特调的位置。"""
        words = ['浓缩咖啡', '汀曼特调', '卡布奇诺']
        op, result, clicked = self._choose_from_list(test_context, monkeypatch, words)
        assert result.is_success and result.status == '汀曼特调', f'应选汀曼特调,实际 {result.status}'
        assert op.chosen_coffee.coffee_name == '汀曼特调'
        assert len(clicked) == 1 and clicked[0].x == self._expected_click_x(test_context, words, '汀曼特调'), \
            f'应点汀曼特调,实际点了 {clicked}'

    def test_choose_coffee_fallback_without_tinman(self, test_context: TestContext,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
        """重试到最后一次列表里仍没有汀曼特调 → 改选浓缩咖啡(issue #3055)。"""
        words = ['卡布奇诺', '浓缩咖啡', '拿铁']
        op, result, clicked = self._choose_from_list(test_context, monkeypatch, words)
        assert result.is_success and result.status == '浓缩咖啡', f'应改选浓缩咖啡,实际 {result.status}'
        assert op.chosen_coffee.coffee_name == '浓缩咖啡'
        assert len(clicked) == 1 and clicked[0].x == self._expected_click_x(test_context, words, '浓缩咖啡'), \
            f'应点浓缩咖啡,实际点了 {clicked}'

    def test_choose_coffee_no_fallback_before_last_round(self, test_context: TestContext,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
        """前几轮没认出汀曼特调（列表可能还在滑入）→ 先重试，不点浓缩咖啡。"""
        _, result, clicked = self._choose_from_list(test_context, monkeypatch, ['浓缩咖啡', '卡布奇诺'],
                                                    last_round=False)
        assert not result.is_success and result.status == '没找到目标咖啡', f'应先重试,实际 {result.status}'
        assert clicked == [], f'重试前不应点击,实际点了 {clicked}'

    def test_choose_coffee_tinman_poor_ocr(self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """汀曼特调只认出「汀曼特」(低阈值才命中) → 仍选汀曼特调，不被高阈值命中的浓缩咖啡抢先。"""
        words = ['汀曼特', '浓缩咖啡']
        _, result, clicked = self._choose_from_list(test_context, monkeypatch, words)
        assert result.is_success and result.status == '汀曼特调', \
            f'OCR 不准时仍应选汀曼特调,实际 {result.status}'
        assert len(clicked) == 1 and clicked[0].x == self._expected_click_x(test_context, words, '汀曼特'), \
            f'应点认出的「汀曼特」,实际点了 {clicked}'

    def test_choose_coffee_nothing_matched(self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """最后一次仍既没有汀曼特调也没有浓缩咖啡 → 没找到目标咖啡。"""
        _, result, clicked = self._choose_from_list(test_context, monkeypatch, ['卡布奇诺', '拿铁'])
        assert not result.is_success and result.status == '没找到目标咖啡', f'实际 {result.status}'
        assert clicked == []

    def test_choose_coffee_fallback_already_had(self, test_context: TestContext,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
        """没有汀曼特调、浓缩咖啡已喝过 → 不再点浓缩咖啡,返回没找到目标咖啡。"""
        _, result, clicked = self._choose_from_list(test_context, monkeypatch, ['浓缩咖啡', '拿铁'],
                                                    had_coffee={'浓缩咖啡'})
        assert not result.is_success and result.status == '没找到目标咖啡', f'实际 {result.status}'
        assert clicked == []
