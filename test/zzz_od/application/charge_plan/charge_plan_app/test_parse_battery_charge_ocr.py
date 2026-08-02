import pytest

from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp


def _ocr_item(text: str, x: float, w: float) -> MatchResult:
    """构造一个 OCR 文本项, 框中心 x+w/2 与字段锚点 (173, 348, 485) 对应"""
    return MatchResult(1.0, x, 25, w, 30, data=text)


def _ocr_map(*items: tuple[str, float, float]) -> dict:
    """构造 OCR 结果 dict, key 为识别文本"""
    result = {}
    for text, x, w in items:
        lst = MatchResultList(only_best=False)
        lst.append(_ocr_item(text, x, w))
        result[text] = lst
    return result


class TestParseBatteryChargeOcr:

    def test_全字段正常(self):
        """三个字段都识别到时, 返回对应数字"""
        ocr = _ocr_map(
            ('129/240', 162, 116),
            ('0', 371, 18),
            ('2', 484, 22),
        )
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (129, 0, 2)

    def test_漏掉储蓄电量(self):
        """中间字段漏识别, 按中心点归位后补 0"""
        ocr = _ocr_map(
            ('129/240', 162, 116),
            ('2', 484, 22),
        )
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (129, 0, 2)

    def test_漏掉电量(self):
        """最左字段漏识别, 补 0"""
        ocr = _ocr_map(
            ('48', 352, 40),
            ('4', 483, 24),
        )
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (0, 48, 4)

    def test_漏掉以太电池(self):
        """最右字段漏识别, 补 0"""
        ocr = _ocr_map(
            ('129/240', 162, 116),
            ('0', 371, 18),
        )
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (129, 0, 0)

    def test_只识别到中间字段(self):
        """只有储蓄电量识别到, 其余补 0"""
        ocr = _ocr_map(('48', 352, 40))
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (0, 48, 0)

    def test_全部识别失败(self):
        """一个都识别不到, 返回 0 0 0 不报错"""
        assert ChargePlanApp._parse_battery_charge_ocr({}) == (0, 0, 0)
        assert ChargePlanApp._parse_battery_charge_ocr(None) == (0, 0, 0)

    def test_噪音文本不影响取数(self):
        """非数字文本(如 ins)被跳过, 不影响数字字段"""
        ocr = _ocr_map(
            ('ins', 235, 21),
            ('129/240', 162, 116),
            ('2', 484, 22),
        )
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (129, 0, 2)

    def test_同一字段多个候选保留近锚点(self):
        """同一字段出现多个数字候选时, 保留离锚点更近的"""
        ocr = _ocr_map(
            ('1', 279, 30),  # 中心 294, 离储蓄锚点 348 较远
            ('38', 334, 45),  # 中心 356.5, 更近储蓄锚点
            ('3/240', 126, 118),
            ('54', 467, 40),
        )
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (3, 38, 54)

    def test_纯数字不带斜杠(self):
        """第一个字段漏了 /240 分母时, 纯数字直接使用"""
        ocr = _ocr_map(
            ('129', 162, 80),  # 中心 202, 归属电量
            ('2', 484, 22),
        )
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (129, 0, 2)

    def test_空文本列表(self):
        """OCR 返回空结构时, 返回 0 0 0"""
        ocr = {'129/240': MatchResultList(), '2': MatchResultList()}
        assert ChargePlanApp._parse_battery_charge_ocr(ocr) == (0, 0, 0)
