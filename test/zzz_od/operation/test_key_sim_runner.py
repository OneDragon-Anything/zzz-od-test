"""测试键鼠脚本的插件化读取（key_sim_runner.py / key_sim_yaml_config.py）。"""

from pathlib import Path

import pytest

from one_dragon.base.operation.application.plugin_info import PluginInfo
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
