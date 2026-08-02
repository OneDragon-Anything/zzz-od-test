from one_dragon.base.debug.debug_trace_bus import DebugTraceBus
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
from one_dragon.base.matcher.template_matcher import TemplateMatcher


def test_template_trace_offset_applied_once() -> None:
    matcher = TemplateMatcher.__new__(TemplateMatcher)
    matcher.debug_trace_bus = DebugTraceBus()
    matcher.debug_trace_bus.set_crop_offset(100, 200)
    result = MatchResultList()
    result.append(MatchResult(0.9, 1, 2, 10, 20))

    matcher._emit_debug_vision("sub", "id", result)

    item = matcher.debug_trace_bus.snapshot().vision_items[0]
    assert (item.x1, item.y1, item.x2, item.y2) == (101, 202, 111, 222)


def test_ocr_trace_offset_applied_once() -> None:
    matcher = OnnxOcrMatcher.__new__(OnnxOcrMatcher)
    matcher.debug_trace_bus = DebugTraceBus()
    matcher.debug_trace_bus.set_crop_offset(100, 200)
    result = OcrMatchResult(0.9, 1, 2, 10, 20, data="text")

    matcher._emit_debug_vision_from_ocr_results([result])

    item = matcher.debug_trace_bus.snapshot().vision_items[0]
    assert (item.x1, item.y1, item.x2, item.y2) == (101, 202, 111, 222)
