"""贝果业务与界面测试共用的文件隔离。"""
from pathlib import Path

import pytest

from one_dragon.utils import os_utils


@pytest.fixture(autouse=True)
def isolated_work_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """配置、记录和失败截图写临时目录；识别资源只读主仓。"""
    root = next(path.parent for path in Path(__file__).resolve().parents if path.name == 'zzz-od-test')
    original_work_path = os_utils.get_path_under_work_dir
    original_resource_path = os_utils.get_resource_path
    monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))

    def work_path(*parts: str) -> str:
        """兼容通过工作目录读取模板的识别器，其余路径保持隔离。"""
        return str(root.joinpath(*parts)) if parts and parts[0] == 'assets' else original_work_path(*parts)

    def resource_path(*parts: str, prefer_bundled: bool = False) -> str:
        """发布流程和图像使用真实资源，配置资源仍留在临时目录。"""
        if parts and parts[0] == 'assets':
            return str(root.joinpath(*parts))
        return original_resource_path(*parts, prefer_bundled=prefer_bundled)

    monkeypatch.setattr(os_utils, 'get_path_under_work_dir', work_path)
    monkeypatch.setattr(os_utils, 'get_resource_path', resource_path)
