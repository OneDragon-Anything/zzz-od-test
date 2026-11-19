"""插件导入服务的覆盖安装行为。

订阅与更新都按覆盖安装处理，这里锁住三件事：
残留的旧版本目录会被换成新版本、带 git 仓库的目录也会被换掉但旧版本留备份、
不覆盖时仍然拒绝已存在的目录（本地导入的语义没变）。
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)


class _TmpImportService(PluginImportService):
    """把 plugins 目录指到临时目录，避免碰到真实的 plugins。"""

    def __init__(self, plugins_dir: Path) -> None:
        PluginImportService.__init__(self, object())  # type: ignore[arg-type]
        self._plugins_dir: Path = plugins_dir

    @property
    def plugins_dir(self) -> Path:
        """临时 plugins 目录。"""
        return self._plugins_dir


def _make_plugin_zip(path: Path, version: str) -> Path:
    """构造一个最小合法插件包（bagel/factory.py + bagel/const.py）。"""
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('bagel/__init__.py', '')
        zf.writestr('bagel/factory.py', '')
        zf.writestr('bagel/const.py', f'APP_ID = "bagel"\nPLUGIN_VERSION = "{version}"\n')
    return path


def _read_version(plugin_dir: Path) -> str:
    """读出插件目录里 const.py 声明的版本号。"""
    for line in (plugin_dir / 'const.py').read_text(encoding='utf-8').splitlines():
        if line.startswith('PLUGIN_VERSION'):
            return line.split('=', 1)[1].strip().strip('"')
    return ''


class TestPluginImportOverwrite:

    def test_overwrite_replaces_residue_dir(self, tmp_path: Path) -> None:
        """残留的旧版本目录在覆盖安装时被换成新版本。"""
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        service = _TmpImportService(plugins_dir)

        old_zip = _make_plugin_zip(tmp_path / 'old.zip', '0.3.2')
        new_zip = _make_plugin_zip(tmp_path / 'new.zip', '0.5.0')
        assert service.import_plugin(old_zip, overwrite=False).success
        assert _read_version(plugins_dir / 'bagel') == '0.3.2'

        result = service.import_plugin(new_zip, overwrite=True)

        assert result.success
        assert _read_version(plugins_dir / 'bagel') == '0.5.0'
        # 普通目录替换成功后不留下备份目录
        assert not [p for p in plugins_dir.iterdir() if 'backup' in p.name]

    def test_overwrite_keeps_git_backup(self, tmp_path: Path) -> None:
        """目录里带 git 仓库时照样覆盖，旧版本连 .git 一起留成备份。"""
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        service = _TmpImportService(plugins_dir)

        old_zip = _make_plugin_zip(tmp_path / 'old.zip', '0.3.2')
        new_zip = _make_plugin_zip(tmp_path / 'new.zip', '0.5.0')
        assert service.import_plugin(old_zip, overwrite=False).success
        git_dir = plugins_dir / 'bagel' / '.git'
        git_dir.mkdir()
        (git_dir / 'HEAD').write_text('ref: refs/heads/main\n', encoding='utf-8')

        result = service.import_plugin(new_zip, overwrite=True)

        assert result.success
        assert _read_version(plugins_dir / 'bagel') == '0.5.0'
        backups = [p for p in plugins_dir.iterdir() if p.name.startswith('.') and 'backup' in p.name]
        assert len(backups) == 1
        assert (backups[0] / '.git' / 'HEAD').is_file()
        assert _read_version(backups[0]) == '0.3.2'

    def test_no_overwrite_rejects_existing_dir(self, tmp_path: Path) -> None:
        """不覆盖时仍然拒绝已存在的目录，本地导入语义不变。"""
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        service = _TmpImportService(plugins_dir)

        old_zip = _make_plugin_zip(tmp_path / 'old.zip', '0.3.2')
        new_zip = _make_plugin_zip(tmp_path / 'new.zip', '0.5.0')
        assert service.import_plugin(old_zip, overwrite=False).success

        result = service.import_plugin(new_zip, overwrite=False)

        assert not result.success
        assert '已存在' in result.message
        assert _read_version(plugins_dir / 'bagel') == '0.3.2'
