"""调试图目录清理。"""

import os
from pathlib import Path

from one_dragon.utils import debug_utils


def _make_images(image_dir: Path, count: int) -> list[Path]:
    """造 count 张 png，修改时间依次递增，返回从旧到新的路径。"""
    image_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    base = 1_700_000_000
    for i in range(count):
        path = image_dir / f'img_{i:03d}.png'
        path.write_bytes(b'x')
        os.utime(path, (base + i, base + i))
        paths.append(path)
    return paths


class TestPruneDebugImages:

    def test_keeps_newest_images(self, tmp_path: Path, monkeypatch) -> None:
        image_dir = tmp_path / 'images'
        paths = _make_images(image_dir, 5)
        monkeypatch.setattr(debug_utils, 'get_debug_image_dir_path', lambda: str(image_dir))

        removed = debug_utils.prune_debug_images(keep_count=2)

        assert removed == 3
        remaining = {p.name for p in image_dir.iterdir()}
        assert remaining == {paths[-1].name, paths[-2].name}

    def test_noop_when_under_limit(self, tmp_path: Path, monkeypatch) -> None:
        image_dir = tmp_path / 'images'
        paths = _make_images(image_dir, 2)
        monkeypatch.setattr(debug_utils, 'get_debug_image_dir_path', lambda: str(image_dir))

        assert debug_utils.prune_debug_images(keep_count=5) == 0
        assert all(p.exists() for p in paths)

    def test_missing_dir_returns_zero(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(debug_utils, 'get_debug_image_dir_path', lambda: str(tmp_path / 'nope'))

        assert debug_utils.prune_debug_images() == 0

    def test_sub_directory_is_ignored(self, tmp_path: Path, monkeypatch) -> None:
        image_dir = tmp_path / 'images'
        _make_images(image_dir, 2)
        (image_dir / 'sub').mkdir()
        monkeypatch.setattr(debug_utils, 'get_debug_image_dir_path', lambda: str(image_dir))

        assert debug_utils.prune_debug_images(keep_count=1) == 1
        assert (image_dir / 'sub').is_dir()
