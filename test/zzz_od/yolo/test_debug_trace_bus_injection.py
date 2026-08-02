from unittest.mock import patch

from one_dragon.base.debug.debug_trace_bus import DebugTraceBus
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import (
    LostVoidDetector,
)
from zzz_od.yolo.hollow_event_detector import HollowEventDetector


def test_lost_void_detector_forwards_debug_trace_bus() -> None:
    bus = DebugTraceBus()
    with patch("one_dragon.yolo.yolov8_onnx_det.Yolov8Detector.__init__", return_value=None) as init:
        LostVoidDetector("model", "backup", debug_trace_bus=bus)

    assert init.call_args.kwargs["debug_trace_bus"] is bus


def test_hollow_event_detector_forwards_debug_trace_bus() -> None:
    bus = DebugTraceBus()
    with patch("one_dragon.yolo.yolov8_onnx_det.Yolov8Detector.__init__", return_value=None) as init:
        HollowEventDetector(debug_trace_bus=bus)

    assert init.call_args.kwargs["debug_trace_bus"] is bus
