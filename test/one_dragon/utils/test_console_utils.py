"""控制台编码兜底。"""

import io
import sys
from typing import Any

from one_dragon.utils.console_utils import ensure_utf8_stdio


class _FakeStream:
    """记录 reconfigure 参数的假控制台流。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error

    def reconfigure(self, **kwargs: Any) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)


class TestEnsureUtf8Stdio:

    def test_switches_stdout_and_stderr_to_utf8(self, monkeypatch) -> None:
        out = _FakeStream()
        err = _FakeStream()
        monkeypatch.setattr(sys, 'stdout', out)
        monkeypatch.setattr(sys, 'stderr', err)

        ensure_utf8_stdio()

        assert out.calls == [{'encoding': 'utf-8', 'errors': 'replace'}]
        assert err.calls == [{'encoding': 'utf-8', 'errors': 'replace'}]

    def test_stream_without_reconfigure_is_skipped(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, 'stdout', io.StringIO())
        monkeypatch.setattr(sys, 'stderr', io.StringIO())

        ensure_utf8_stdio()

    def test_reconfigure_error_is_ignored(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, 'stdout', _FakeStream(error=ValueError('closed')))
        monkeypatch.setattr(sys, 'stderr', _FakeStream(error=OSError('closed')))

        ensure_utf8_stdio()

    def test_none_stream_is_ignored(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, 'stdout', None)
        monkeypatch.setattr(sys, 'stderr', None)

        ensure_utf8_stdio()