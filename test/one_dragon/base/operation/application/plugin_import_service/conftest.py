from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import pytest

from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)


class StubPluginImportService(PluginImportService):
    """使用临时插件目录的导入服务。"""

    def __init__(self, plugins_dir: Path) -> None:
        self._plugins_dir: Path = plugins_dir

    @property
    def plugins_dir(self) -> Path:
        return self._plugins_dir


@pytest.fixture
def plugin_import_service(tmp_path: Path) -> StubPluginImportService:
    return StubPluginImportService(tmp_path / "plugins")


@pytest.fixture
def create_zip() -> Callable[[Path, dict[str, str]], None]:
    def create(path: Path, files: dict[str, str]) -> None:
        with ZipFile(path, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)

    return create
