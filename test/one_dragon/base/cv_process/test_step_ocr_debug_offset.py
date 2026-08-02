from concurrent.futures import ThreadPoolExecutor

from one_dragon.base.cv_process.steps.step_ocr import CvStepOcr
from one_dragon.base.debug.debug_trace_bus import DebugTraceBus


class FakeOcr:
    def __init__(self, bus: DebugTraceBus) -> None:
        self.debug_trace_bus = bus
        self.offset_during_run: tuple[int, int] | None = None

    def run_ocr(self, image: object) -> dict:
        self.offset_during_run = self.debug_trace_bus.crop_offset
        return {}


def test_run_ocr_with_trace_offset_restores_worker_scope() -> None:
    bus = DebugTraceBus()
    ocr = FakeOcr(bus)
    bus.set_crop_offset(100, 200)

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            CvStepOcr._run_ocr_with_trace_offset,
            ocr,
            object(),
            (110, 220),
        ).result()
        worker_offset = executor.submit(lambda: bus.crop_offset).result()

    assert result == {}
    assert ocr.offset_during_run == (110, 220)
    assert worker_offset == (0, 0)
    assert bus.crop_offset == (100, 200)
