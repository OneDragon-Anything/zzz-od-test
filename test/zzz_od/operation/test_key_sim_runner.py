"""测试键鼠脚本的插件化读取（key_sim_runner.py / key_sim_yaml_config.py）。"""

import sys
from pathlib import Path
from types import ModuleType

import pytest

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginInfo, PluginSource
from zzz_od.operation.key_sim_runner import KeySimRunner
from zzz_od.operation.key_sim_yaml_config import KeySimYamlConfig


def _write_yml(path: Path, operations: list[dict]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({'operations': operations}, allow_unicode=True),
                    encoding='utf-8')


def _make_plugin_info(plugin_dir: Path, key_sim_dir: str = 'scripts') -> PluginInfo:
    """构造一个注册了键鼠脚本目录的插件信息。"""
    return PluginInfo(
        app_id='fake_plugin',
        app_name='假插件',
        default_group=True,
        plugin_dir=plugin_dir,
        key_sim_dir=key_sim_dir,
    )


class TestKeySimYamlConfig:
    """键鼠脚本配置的路径解析（用户 / 插件目录 / sample 回退）。"""

    def test_user_yml_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from one_dragon.utils import os_utils

        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        _write_yml(tmp_path / 'config' / 'key_sim' / '脚本.yml', [{'op_name': 'a'}])
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'scripts' / '脚本.yml', [{'op_name': 'b'}])

        config = KeySimYamlConfig('脚本', plugin_dir=plugin_dir / 'scripts')
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': 'a'}]

    def test_plugin_yml_in_nested_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from one_dragon.utils import os_utils

        # 插件目录内任意子目录都可放脚本，不限定目录名
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'scripts' / '嵌套' / '脚本.yml', [{'op_name': 'b'}])

        config = KeySimYamlConfig('脚本', plugin_dir=plugin_dir / 'scripts')
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': 'b'}]

    def test_plugin_yml_at_plugin_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from one_dragon.utils import os_utils

        # 直接放脚本目录根部也可以
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'scripts' / '脚本.yml', [{'op_name': 'b'}])

        config = KeySimYamlConfig('脚本', plugin_dir=plugin_dir / 'scripts')
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': 'b'}]

    def test_sample_yml_not_matched(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from one_dragon.utils import os_utils

        # 插件目录里的 .sample.yml 不算脚本（插件分发正式脚本），回退仓库 sample
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        _write_yml(tmp_path / 'config' / 'key_sim' / '脚本.sample.yml', [{'op_name': 'a'}])
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'scripts' / '脚本.sample.yml', [{'op_name': 'b'}])

        config = KeySimYamlConfig('脚本', plugin_dir=plugin_dir / 'scripts')
        assert config.is_sample is True
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': 'a'}]

    def test_no_plugin_dir_skips_plugin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from one_dragon.utils import os_utils

        # 插件没注册脚本目录时跳过插件查找，回退仓库 sample
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        _write_yml(tmp_path / 'config' / 'key_sim' / '真拿命验收.sample.yml', [{'op_name': '等待秒数', 'seconds': 0.1}])

        config = KeySimYamlConfig('真拿命验收', plugin_dir=None)
        assert config.is_sample is True
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': '等待秒数', 'seconds': 0.1}]

    def test_missing_all_points_to_user_yml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from one_dragon.utils import os_utils

        # 用户 / 插件 / sample 都没有时，读取路径指向用户 config/key_sim/<name>.yml
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))

        config = KeySimYamlConfig('不存在的脚本', plugin_dir=None)
        assert config.file_path == str(tmp_path / 'config' / 'key_sim' / '不存在的脚本.yml')

    def test_duplicate_plugin_yml_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from one_dragon.utils import os_utils

        # 同一脚本目录内多个同名脚本 → 显式报错，避免按未声明顺序执行
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'scripts' / 'a' / '脚本.yml', [{'op_name': 'a'}])
        _write_yml(plugin_dir / 'scripts' / 'b' / '脚本.yml', [{'op_name': 'b'}])

        with pytest.raises(ValueError, match='重名'):
            KeySimYamlConfig('脚本', plugin_dir=plugin_dir / 'scripts')


class TestKeySimRunnerLoadConfig:
    """KeySimRunner 的配置加载（按当前运行应用查插件注册目录）。"""

    def test_reads_plugin_yml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        from one_dragon.utils import os_utils

        # 当前应用注册了键鼠脚本目录，插件目录提供脚本
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'scripts' / '插件脚本.yml', [{'op_name': '等待秒数', 'seconds': 0.1}])
        plugin_info = _make_plugin_info(plugin_dir)
        monkeypatch.setattr(test_context.run_context, 'current_app_id', plugin_info.app_id)
        monkeypatch.setattr(test_context.factory_manager, 'get_plugin_info',
                            lambda app_id: plugin_info if app_id == plugin_info.app_id else None)

        runner = KeySimRunner(test_context, '插件脚本')
        config = runner._load_key_sim_config()
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': '等待秒数', 'seconds': 0.1}]

    def test_reads_user_yml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        from one_dragon.utils import os_utils

        # 用户 config 目录提供脚本，覆盖插件同名脚本
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        _write_yml(tmp_path / 'config' / 'key_sim' / '脚本.yml', [{'op_name': '等待秒数', 'seconds': 0.5}])
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'scripts' / '脚本.yml', [{'op_name': '等待秒数', 'seconds': 0.1}])
        plugin_info = _make_plugin_info(plugin_dir)
        monkeypatch.setattr(test_context.run_context, 'current_app_id', plugin_info.app_id)
        monkeypatch.setattr(test_context.factory_manager, 'get_plugin_info',
                            lambda app_id: plugin_info if app_id == plugin_info.app_id else None)

        runner = KeySimRunner(test_context, '脚本')
        config = runner._load_key_sim_config()
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': '等待秒数', 'seconds': 0.5}]

    def test_plugin_without_key_sim_dir_falls_back_to_sample(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        from one_dragon.utils import os_utils

        # 当前应用存在但没注册键鼠脚本目录 → 跳过插件查找，回退仓库 sample
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        _write_yml(tmp_path / 'config' / 'key_sim' / '真拿命验收.sample.yml', [{'op_name': '等待秒数', 'seconds': 0.1}])
        plugin_info = _make_plugin_info(tmp_path / 'plugins' / 'my_plugin', key_sim_dir='')
        monkeypatch.setattr(test_context.run_context, 'current_app_id', plugin_info.app_id)
        monkeypatch.setattr(test_context.factory_manager, 'get_plugin_info',
                            lambda app_id: plugin_info if app_id == plugin_info.app_id else None)

        runner = KeySimRunner(test_context, '真拿命验收')
        config = runner._load_key_sim_config()
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': '等待秒数', 'seconds': 0.1}]

    def test_no_current_app_falls_back_to_sample(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        from one_dragon.utils import os_utils

        # 不在应用执行链里（current_app_id 为 None）→ 跳过插件查找，回退仓库 sample
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        _write_yml(tmp_path / 'config' / 'key_sim' / '真拿命验收.sample.yml', [{'op_name': '等待秒数', 'seconds': 0.1}])
        monkeypatch.setattr(test_context.run_context, 'current_app_id', None)

        runner = KeySimRunner(test_context, '真拿命验收')
        config = runner._load_key_sim_config()
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': '等待秒数', 'seconds': 0.1}]


class TestRegisterKeySimDir:
    """插件注册时 KEY_SIM_DIR 的合法性校验。"""

    @staticmethod
    def _make_const_module(key_sim_dir_value: object) -> ModuleType:
        const_mod = ModuleType('fake_pkg.fake_const')
        const_mod.APP_ID = 'fake_plugin'
        const_mod.APP_NAME = '假插件'
        const_mod.DEFAULT_GROUP = True
        const_mod.NEED_NOTIFY = True
        const_mod.KEY_SIM_DIR = key_sim_dir_value
        return const_mod

    def _register(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        test_context,
        key_sim_dir_value: object,
    ) -> PluginInfo:
        """构造工厂与 const 模块，走插件注册流程返回 PluginInfo。"""
        const_mod = self._make_const_module(key_sim_dir_value)
        monkeypatch.setitem(sys.modules, 'fake_pkg.fake_const', const_mod)
        (tmp_path / 'fake_const.py').write_text('', encoding='utf-8')
        factory = ApplicationFactory(const_mod)
        manager = ApplicationFactoryManager(test_context, [])
        return manager._register_plugin_metadata(
            factory, tmp_path / 'fake_factory.py', 'fake_pkg.fake_factory',
            PluginSource.THIRD_PARTY,
        )

    def test_valid_relative_dir_registered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        plugin_info = self._register(tmp_path, monkeypatch, test_context, 'scripts')
        assert plugin_info.key_sim_dir == 'scripts'

    def test_empty_dir_registered(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context) -> None:
        # 未声明 KEY_SIM_DIR 时按空字符串处理，不拦截注册
        plugin_info = self._register(tmp_path, monkeypatch, test_context, '')
        assert plugin_info.key_sim_dir == ''

    def test_non_string_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        with pytest.raises(ImportError, match='必须是字符串'):
            self._register(tmp_path, monkeypatch, test_context, 123)

    def test_absolute_path_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        with pytest.raises(ImportError, match='必须是相对路径'):
            self._register(tmp_path, monkeypatch, test_context, 'C:/etc/scripts')

    def test_parent_path_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        with pytest.raises(ImportError, match='必须是相对路径'):
            self._register(tmp_path, monkeypatch, test_context, '../scripts')
