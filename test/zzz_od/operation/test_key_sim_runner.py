"""测试键鼠脚本的插件化读取（key_sim_runner.py）。"""

from pathlib import Path

import pytest

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from zzz_od.operation.key_sim_runner import KeySimRunner, find_key_sim_yml


def _write_yml(path: Path, operations: list[dict]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({'operations': operations}, allow_unicode=True),
                    encoding='utf-8')


class TestFindKeySimYml:
    """脚本路径定位（纯函数）。"""

    def test_user_yml_priority(self, tmp_path: Path) -> None:
        _write_yml(tmp_path / 'config' / 'key_sim' / '脚本.yml', [{'op_name': 'a'}])
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'key_sim' / '脚本.yml', [{'op_name': 'b'}])

        result = find_key_sim_yml(tmp_path, [plugin_dir], '脚本')
        assert result == tmp_path / 'config' / 'key_sim' / '脚本.yml'

    def test_plugin_yml_when_user_missing(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'key_sim' / '脚本.yml', [{'op_name': 'b'}])

        result = find_key_sim_yml(tmp_path, [plugin_dir], '脚本')
        assert result == plugin_dir / 'key_sim' / '脚本.yml'

    def test_first_plugin_dir_wins(self, tmp_path: Path) -> None:
        plugin_a = tmp_path / 'plugins' / 'plugin_a'
        plugin_b = tmp_path / 'plugins' / 'plugin_b'
        _write_yml(plugin_a / 'key_sim' / '脚本.yml', [{'op_name': 'a'}])
        _write_yml(plugin_b / 'key_sim' / '脚本.yml', [{'op_name': 'b'}])

        result = find_key_sim_yml(tmp_path, [plugin_a, plugin_b], '脚本')
        assert result == plugin_a / 'key_sim' / '脚本.yml'

    def test_sample_yml_not_matched(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'key_sim' / '脚本.sample.yml', [{'op_name': 'b'}])

        result = find_key_sim_yml(tmp_path, [plugin_dir], '脚本')
        assert result is None

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        result = find_key_sim_yml(tmp_path, [plugin_dir], '不存在的脚本')
        assert result is None


class TestKeySimRunnerLoadConfig:
    """KeySimRunner 的配置加载（用户 / 插件 / sample 回退）。"""

    def test_reads_plugin_yml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_context
    ) -> None:
        from one_dragon.utils import os_utils

        # 用户目录没有该脚本，插件目录提供
        monkeypatch.setattr(os_utils, 'get_work_dir', lambda: str(tmp_path))
        plugin_dir = tmp_path / 'plugins' / 'my_plugin'
        _write_yml(plugin_dir / 'key_sim' / '插件脚本.yml', [{'op_name': '等待秒数', 'seconds': 0.1}])
        monkeypatch.setattr(
            ApplicationFactoryManager, 'plugin_infos',
            [type('FakePluginInfo', (), {'plugin_dir': plugin_dir})()],
            raising=False,
        )

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
        _write_yml(plugin_dir / 'key_sim' / '脚本.yml', [{'op_name': '等待秒数', 'seconds': 0.1}])
        monkeypatch.setattr(
            ApplicationFactoryManager, 'plugin_infos',
            [type('FakePluginInfo', (), {'plugin_dir': plugin_dir})()],
            raising=False,
        )

        runner = KeySimRunner(test_context, '脚本')
        config = runner._load_key_sim_config()
        operations = config.data.get('operations', [])
        assert operations == [{'op_name': '等待秒数', 'seconds': 0.5}]

    def test_falls_back_to_sample(self, monkeypatch: pytest.MonkeyPatch, test_context) -> None:
        # 用户与插件都没有 → 回退仓库自带的 sample 文件（真实工作目录下只读）
        monkeypatch.setattr(ApplicationFactoryManager, 'plugin_infos', [], raising=False)

        runner = KeySimRunner(test_context, '真拿命验收')
        config = runner._load_key_sim_config()
        operations = config.data.get('operations', [])
        assert isinstance(operations, list) and len(operations) > 0
