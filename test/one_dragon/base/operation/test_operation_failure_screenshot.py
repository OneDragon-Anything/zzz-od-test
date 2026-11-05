"""失败时的诊断截图。"""

import numpy as np

from one_dragon.base.operation.operation import Operation


class _FakeNode:
    """只带节点名的假节点。"""

    def __init__(self, cn: str) -> None:
        self.cn = cn


def _make_operation(has_screenshot: bool) -> Operation:
    op = object.__new__(Operation)
    op.last_screenshot = np.zeros((10, 10, 3), dtype=np.uint8) if has_screenshot else None
    op._current_node = _FakeNode('等待画面')
    op.__dict__['display_name'] = '测试指令'
    return op


class TestSaveFailureScreenshot:

    def test_saves_with_node_prefix(self) -> None:
        op = _make_operation(has_screenshot=True)
        saved: list[str | None] = []

        def fake_save(prefix: str | None = None) -> str:
            saved.append(prefix)
            return f'{prefix}.png'

        op.save_screenshot = fake_save
        op._save_failure_screenshot('重试3次未通过')

        assert saved == ['fail_Operation_等待画面']

    def test_skips_without_screenshot(self) -> None:
        op = _make_operation(has_screenshot=False)
        called: list[str | None] = []

        def fake_save(prefix: str | None = None) -> str:
            called.append(prefix)
            return ''

        op.save_screenshot = fake_save
        op._save_failure_screenshot('执行失败')

        assert called == []

    def test_save_error_does_not_break_operation(self) -> None:
        op = _make_operation(has_screenshot=True)

        def broken_save(prefix: str | None = None) -> str:
            raise OSError('磁盘满了')

        op.save_screenshot = broken_save
        op._save_failure_screenshot('执行失败')

    def test_no_current_node_uses_none(self) -> None:
        op = _make_operation(has_screenshot=True)
        op._current_node = None
        saved: list[str | None] = []
        op.save_screenshot = lambda prefix=None: saved.append(prefix) or ''

        op._save_failure_screenshot('执行超时')

        assert saved == ['fail_Operation_none']
