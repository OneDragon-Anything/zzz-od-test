"""插件扫描对隐藏目录的处理。

覆盖安装会在 plugins 下留下 .<插件名>.backup-<uuid> 备份，这类隐藏目录不是插件，
扫描时必须跳过，否则每次扫描都会把备份里的 factory.py 当插件加载并留下失败记录。
"""

from __future__ import annotations

from pathlib import Path

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginSource

FACTORY_SOURCE = '''\
from one_dragon.base.operation.application.application_factory import ApplicationFactory

from . import const


class DemoFactory(ApplicationFactory):

    def __init__(self, ctx) -> None:
        ApplicationFactory.__init__(self, const)
        self.ctx = ctx
'''

CONST_SOURCE = '''\
APP_ID = "demo"
APP_NAME = "演示插件"
DEFAULT_GROUP = True
NEED_NOTIFY = False
'''


class _FakeCtx:
    """只承载工厂实例化所需的空上下文。"""


def _make_plugin(plugin_dir: Path) -> None:
    """在指定目录里造一个最小可加载插件。"""
    plugin_dir.mkdir(parents=True)
    (plugin_dir / '__init__.py').write_text('', encoding='utf-8')
    (plugin_dir / 'factory.py').write_text(FACTORY_SOURCE, encoding='utf-8')
    (plugin_dir / 'const.py').write_text(CONST_SOURCE, encoding='utf-8')


class TestPluginScanHiddenDir:

    def test_hidden_backup_dir_is_skipped(self, tmp_path: Path) -> None:
        """隐藏备份目录不被当作插件扫描，也不产生失败记录。"""
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        _make_plugin(plugins_dir / 'demo')
        _make_plugin(plugins_dir / '.demo.backup-0123456789ab')

        manager = ApplicationFactoryManager(
            _FakeCtx(),
            [(plugins_dir, PluginSource.THIRD_PARTY)],
        )
        factories = manager.discover_factories()

        assert [factory.app_id for factory in factories] == ['demo']
        assert manager.scan_failures == []
