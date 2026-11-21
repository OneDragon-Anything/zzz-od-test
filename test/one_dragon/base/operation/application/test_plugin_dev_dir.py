"""plugins/.dev 下开发版插件的注册规则。

开发版放在 plugins/.dev/<id>/，注册成 <id>_dev，能和商店版同时加载；
插件内部 `from .const import APP_ID` 也必须拿到加过后缀的值，
否则配置、运行记录、数据目录会和商店版串在一起。
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginSource

FACTORY_SOURCE = '''\
from one_dragon.base.operation.application.application_factory import ApplicationFactory

from . import config
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

CONFIG_SOURCE = '''\
from .const import APP_ID
'''


class _FakeCtx:
    """只承载工厂实例化所需的空上下文。"""


def _make_plugin(plugin_dir: Path) -> None:
    """在指定目录里造一个最小可加载插件。"""
    plugin_dir.mkdir(parents=True)
    (plugin_dir / '__init__.py').write_text('', encoding='utf-8')
    (plugin_dir / 'factory.py').write_text(FACTORY_SOURCE, encoding='utf-8')
    (plugin_dir / 'const.py').write_text(CONST_SOURCE, encoding='utf-8')
    (plugin_dir / 'config.py').write_text(CONFIG_SOURCE, encoding='utf-8')


@pytest.fixture(autouse=True)
def _clean_modules() -> Iterator[None]:
    """清掉本文件加载过的插件模块，避免用例之间互相串。"""
    prefixes = ('demo', 'dev_demo')
    for name in list(sys.modules):
        if name in prefixes or name.startswith(tuple(f'{p}.' for p in prefixes)):
            del sys.modules[name]
    yield
    for name in list(sys.modules):
        if name in prefixes or name.startswith(tuple(f'{p}.' for p in prefixes)):
            del sys.modules[name]


class TestDevPluginRegistration:

    def test_dev_plugin_coexists_with_store_version(self, tmp_path: Path) -> None:
        """商店版与开发版同时加载，开发版注册成 demo_dev 并标为开发版。"""
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        _make_plugin(plugins_dir / 'demo')
        dev_dir = plugins_dir / '.dev'
        dev_dir.mkdir()
        _make_plugin(dev_dir / 'demo')

        manager = ApplicationFactoryManager(
            _FakeCtx(),
            [(plugins_dir, PluginSource.THIRD_PARTY), (dev_dir, PluginSource.DEV)],
        )
        factories = manager.discover_factories()

        assert [factory.app_id for factory in factories] == ['demo', 'demo_dev']
        assert manager.scan_failures == []

        infos = {info.app_id: info for info in manager.plugin_infos}
        assert infos['demo'].is_dev is False
        assert infos['demo'].app_name == '演示插件'
        assert infos['demo_dev'].is_dev is True
        assert infos['demo_dev'].app_name == '演示插件（开发版）'
        assert infos['demo_dev'].plugin_dir == dev_dir / 'demo'

    def test_dev_plugin_internal_const_gets_suffix(self, tmp_path: Path) -> None:
        """插件内部 from .const import APP_ID 拿到加后缀的值，配置与数据目录才会隔离。"""
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        _make_plugin(plugins_dir / 'demo')
        dev_dir = plugins_dir / '.dev'
        dev_dir.mkdir()
        _make_plugin(dev_dir / 'demo')

        manager = ApplicationFactoryManager(
            _FakeCtx(),
            [(plugins_dir, PluginSource.THIRD_PARTY), (dev_dir, PluginSource.DEV)],
        )
        manager.discover_factories()

        assert sys.modules['demo.const'].APP_ID == 'demo'
        assert sys.modules['dev_demo.const'].APP_ID == 'demo_dev'
        # 直接 from .const import APP_ID 的模块也要拿到改后的值
        assert sys.modules['dev_demo.config'].APP_ID == 'demo_dev'
