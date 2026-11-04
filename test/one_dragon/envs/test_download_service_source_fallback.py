"""环境下载源回退：当前源失败后按候选顺序换源，并记住成功的源。"""

from copy import deepcopy

import pytest

import one_dragon.envs.repo_config as repo_config_module
from one_dragon.envs.download_service import DownloadService
from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.repo_config import RepoConfig

GITHUB = 'https://github.example/env'
CNB = 'https://cnb.example/env'
GITEE = 'https://gitee.example/env'


class _FakeProjectConfig:
    project_name = 'ZZZ-Test'


class _FakeEnvConfig:
    """只实现 download_env_file 用到的部分。"""

    def __init__(self, current: str, candidates: list[str]):
        self.env_source: str = current
        self.last_env_source: str = ''
        self._candidates: list[str] = candidates

    def get_env_source_candidates(self) -> list[str]:
        return list(self._candidates)


def _make_service(
        env_config: _FakeEnvConfig,
        results: list[bool],
) -> tuple[DownloadService, list[str]]:
    service = DownloadService(_FakeProjectConfig(), env_config)  # type: ignore[arg-type]
    calls: list[str] = []

    def fake_download(
            download_url: str,
            save_file_path: str,
            progress_callback=None,
    ) -> bool:
        calls.append(download_url)
        return results[len(calls) - 1]

    service.download_file_from_url = fake_download  # type: ignore[method-assign]
    return service, calls


class TestDownloadEnvFileFallback:

    def test_current_source_works_without_fallback(self):
        env_config = _FakeEnvConfig(GITHUB, [GITHUB, CNB])
        service, calls = _make_service(env_config, [True])

        assert service.download_env_file('env.zip', 'tmp/env.zip') is True
        assert calls == [f'{GITHUB}/ZZZ-Test/env.zip']
        assert env_config.last_env_source == GITHUB

    def test_falls_back_to_next_source_and_records_it(self):
        env_config = _FakeEnvConfig(GITHUB, [GITHUB, CNB, GITEE])
        service, calls = _make_service(env_config, [False, True])

        assert service.download_env_file('cpython-test.zip', 'tmp/python.zip') is True
        assert calls == [
            f'{GITHUB}/ZZZ-Test/cpython-test.zip',
            f'{CNB}/ZZZ-Test/cpython-test.zip',
        ]
        assert env_config.last_env_source == CNB
        assert env_config.env_source == GITHUB, '不覆盖用户选择的源'

    def test_returns_false_when_all_sources_fail(self):
        env_config = _FakeEnvConfig(GITHUB, [GITHUB, CNB, GITEE])
        service, calls = _make_service(env_config, [False, False, False])

        assert service.download_env_file('env.zip', 'tmp/env.zip') is False
        assert len(calls) == 3
        assert env_config.last_env_source == ''

    def test_last_success_source_is_tried_again(self):
        env_config = _FakeEnvConfig(GITHUB, [GITHUB, CNB])
        env_config.last_env_source = CNB
        service, calls = _make_service(env_config, [False, True])

        assert service.download_env_file('env.zip', 'tmp/env.zip') is True
        assert calls[1].startswith(CNB)


def _load_repo_config(monkeypatch: pytest.MonkeyPatch) -> RepoConfig:
    data = {
        'repositories': {
            'primary': 'github',
            'primary_branch': 'main',
            'branches': {'main': {'label': '主分支', 'desc': '同步'}},
            'options': {
                'github': {
                    'label': 'GitHub',
                    'url': 'https://github.example/repo.git',
                    'use_proxy': True,
                },
            },
        },
        'env_source': {
            'default': 'cnb',
            'options': {
                'github': {'label': 'GitHub', 'value': GITHUB},
                'cnb': {'label': 'CNB', 'value': CNB},
                'gitee': {'label': 'Gitee', 'value': GITEE},
            },
        },
        'regions': {
            'default': {'label': '默认', 'repository': 'github', 'values': {}},
        },
    }

    def fake_yaml_config_init(config: RepoConfig, module_name: str, **kwargs) -> None:
        assert module_name == 'repository'
        config.data = deepcopy(data)

    monkeypatch.setattr(repo_config_module.YamlConfig, '__init__', fake_yaml_config_init)
    return RepoConfig()


class TestSourceOrder:

    def test_current_then_last_success_then_yaml_order(self, monkeypatch: pytest.MonkeyPatch):
        repo_config = _load_repo_config(monkeypatch)

        assert repo_config.get_source_order('env_source', GITEE, GITHUB) == [GITEE, GITHUB, CNB]

    def test_deduplicates_current_from_yaml_order(self, monkeypatch: pytest.MonkeyPatch):
        repo_config = _load_repo_config(monkeypatch)

        assert repo_config.get_source_order('env_source', GITHUB, '') == [GITHUB, CNB, GITEE]

    def test_empty_last_success_is_skipped(self, monkeypatch: pytest.MonkeyPatch):
        repo_config = _load_repo_config(monkeypatch)

        assert repo_config.get_source_order('env_source', GITEE, '') == [GITEE, GITHUB, CNB]

    def test_env_config_candidates_use_current_and_last_success(self):
        class _RecordingRepoConfig:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, str]] = []

            def get_source_default(self, source_name: str) -> str:
                return CNB

            def get_source_order(self, source_name: str, current: str, last_success: str) -> list[str]:
                self.calls.append((source_name, current, last_success))
                return [current, last_success, GITEE]

        env_config = object.__new__(EnvConfig)
        env_config.data = {'env_source': GITHUB, 'last_env_source': CNB}
        env_config.repo_config = _RecordingRepoConfig()

        assert env_config.get_env_source_candidates() == [GITHUB, CNB, GITEE]
        assert env_config.repo_config.calls == [('env_source', GITHUB, CNB)]
