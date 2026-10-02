from unittest.mock import MagicMock

import numpy as np
import pytest

from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.bagel.bagel_enter import BagelEnter


@pytest.mark.parametrize('save_error', [False, True])
def test_failure_keeps_cleanup_when_capture_fails(
    monkeypatch: pytest.MonkeyPatch, save_error: bool,
) -> None:
    """识别失败留图；磁盘故障也必须完成事件清理和结果回调。"""
    ctx = MagicMock()
    ctx.run_context.event_bus = ContextEventBus()
    op = BagelEnter(ctx)
    op._init_before_execute()
    op.last_screenshot = np.zeros((2, 2, 3), dtype=np.uint8)
    capture = MagicMock(return_value='failure.png')
    if save_error:
        capture.side_effect = OSError('磁盘不可写')
    monkeypatch.setattr(op, 'save_screenshot', capture)
    callback = MagicMock()
    op.op_callback = callback
    result = OperationResult(False, '未识别备战页')

    op.after_operation_done(result)

    capture.assert_called_once_with()
    assert not any(ctx.run_context.event_bus.callbacks.values())
    callback.assert_called_once_with(result)


@pytest.mark.parametrize('success,has_image', [(True, True), (False, False)])
def test_success_or_missing_frame_does_not_save(
    monkeypatch: pytest.MonkeyPatch, success: bool, has_image: bool,
) -> None:
    """成功或还没拿到截图时，不制造无效现场文件。"""
    ctx = MagicMock()
    ctx.run_context.event_bus = ContextEventBus()
    op = BagelEnter(ctx)
    op._init_before_execute()
    op.last_screenshot = np.zeros((2, 2, 3), dtype=np.uint8) if has_image else None
    capture = MagicMock()
    monkeypatch.setattr(op, 'save_screenshot', capture)

    op.after_operation_done(OperationResult(success))

    capture.assert_not_called()
    assert not any(ctx.run_context.event_bus.callbacks.values())
