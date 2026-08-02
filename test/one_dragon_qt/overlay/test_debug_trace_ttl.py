from one_dragon.base.debug.debug_trace_bus import PerfTraceItem, VisionTraceItem
from one_dragon_qt.overlay.overlay_manager import _filter_recent_items


def test_filter_recent_items_uses_consumer_ttl() -> None:
    items = [
        VisionTraceItem("ocr", "fresh", 0, 0, 1, 1, created=99.0),
        VisionTraceItem("ocr", "expired", 0, 0, 1, 1, created=98.0),
    ]

    recent = _filter_recent_items(items, now=100.0, ttl_seconds=1.8)

    assert [item.label for item in recent] == ["fresh"]


def test_filter_recent_perf_items() -> None:
    items = [
        PerfTraceItem("fresh", 1.0, created=80.0),
        PerfTraceItem("expired", 2.0, created=69.0),
    ]

    recent = _filter_recent_items(items, now=100.0, ttl_seconds=30.0)

    assert [item.metric for item in recent] == ["fresh"]
