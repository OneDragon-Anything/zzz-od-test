"""截图保存失败时不能给出虚构路径。"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zzz_od.application.bagel import bagel_usage


@pytest.mark.parametrize('exists', [False, True])
def test_log_screenshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exists: bool) -> None:
    """接口返回文件名不等于写入成功。"""
    path = tmp_path / 'scene.png'
    if exists:
        path.write_bytes(b'fixture')
    logger = MagicMock()
    monkeypatch.setattr(bagel_usage, 'log', logger)
    monkeypatch.setattr(bagel_usage.debug_utils, 'get_debug_image_path', lambda name: str(path))
    bagel_usage.log_screenshot('scene')
    assert logger.info.call_count == int(exists)
    assert logger.warning.call_count == int(not exists)
    if exists:
        assert logger.info.call_args.args[1] == path.resolve()
