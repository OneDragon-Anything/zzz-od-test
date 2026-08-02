import threading

from one_dragon.base.debug.debug_trace_bus import (
    DebugTraceBus,
    DecisionTraceItem,
    PerfTraceItem,
    TimelineTraceItem,
    VisionTraceItem,
)


def test_snapshot_and_clear() -> None:
    bus = DebugTraceBus()
    bus.add_vision(VisionTraceItem("ocr", "text", 1, 2, 3, 4))
    bus.add_decision(DecisionTraceItem("op", "a", "b", "c", "ok"))
    bus.add_timeline(TimelineTraceItem("node", "title"))
    bus.add_perf(PerfTraceItem("ocr_ms", 12.3, "ms"))

    snapshot = bus.snapshot()
    assert snapshot.vision_items[0].created > 0
    assert snapshot.decision_items[0].created > 0
    assert snapshot.timeline_items[0].created > 0
    assert snapshot.perf_items[0].metric == "ocr_ms"

    bus.clear()
    snapshot = bus.snapshot()
    assert not snapshot.vision_items
    assert not snapshot.decision_items
    assert not snapshot.timeline_items
    assert not snapshot.perf_items


def test_nested_crop_offset_applied_once_and_restored() -> None:
    bus = DebugTraceBus()
    bus.set_crop_offset(100, 200)
    bus.set_crop_offset(110, 220)
    bus.add_vision(VisionTraceItem("ocr", "text", 1, 2, 11, 12))
    assert bus.snapshot().vision_items[0].x1 == 111
    assert bus.snapshot().vision_items[0].y1 == 222

    bus.reset_crop_offset()
    assert bus.crop_offset == (100, 200)
    bus.reset_crop_offset()
    assert bus.crop_offset == (0, 0)
    bus.reset_crop_offset()
    assert bus.crop_offset == (0, 0)


def test_crop_offset_is_thread_local() -> None:
    bus = DebugTraceBus()
    offsets: list[tuple[int, int]] = []

    def worker(offset: tuple[int, int]) -> None:
        bus.set_crop_offset(*offset)
        offsets.append(bus.crop_offset)
        bus.reset_crop_offset()

    threads = [threading.Thread(target=worker, args=((10, 20),)), threading.Thread(target=worker, args=((30, 40),))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(offsets) == [(10, 20), (30, 40)]
    assert bus.crop_offset == (0, 0)
