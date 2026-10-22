from copy import deepcopy

import pytest

import one_dragon.envs.repo_config as repo_config_module
from one_dragon.envs.repo_config import RepoConfig


def _create_config_data(
    primary_branch: object = 'develop',
    branches: object | None = None,
) -> dict[str, object]:
    if branches is None:
        branches = {
            'develop': {
                'label': '稳定分支',
                'desc': '同步稳定版本',
            },
            'test': {
                'label': '测试分支',
                'desc': '同步测试版本',
            },
        }
    return {
        'repositories': {
            'primary': 'github',
            'primary_branch': primary_branch,
            'branches': branches,
            'options': {
                'github': {
                    'label': 'GitHub',
                    'url': 'https://github.example/repo.git',
                    'use_proxy': True,
                },
            },
        },
        'regions': {
            'default': {
                'label': '默认',
                'repository': 'github',
                'values': {},
            },
        },
    }


def _load_repo_config(
    monkeypatch: pytest.MonkeyPatch,
    config_data: dict[str, object],
) -> RepoConfig:
    def fake_yaml_config_init(config: RepoConfig, module_name: str) -> None:
        assert module_name == 'repository'
        config.data = deepcopy(config_data)

    monkeypatch.setattr(repo_config_module.YamlConfig, '__init__', fake_yaml_config_init)
    return RepoConfig()


def test_repo_config_reads_primary_branch_and_branch_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_config = _load_repo_config(monkeypatch, _create_config_data())

    assert repo_config.primary_branch == 'develop'
    assert [
        (option.label, option.value, option.desc)
        for option in repo_config.branch_options
    ] == [
        ('稳定分支', 'develop', '同步稳定版本'),
        ('测试分支', 'test', '同步测试版本'),
    ]


def test_repo_config_requires_primary_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    config_data = _create_config_data()
    repositories = config_data['repositories']
    assert isinstance(repositories, dict)
    del repositories['primary_branch']

    with pytest.raises(ValueError, match='primary_branch'):
        _load_repo_config(monkeypatch, config_data)


@pytest.mark.parametrize('primary_branch', [None, '', '   '])
def test_repo_config_rejects_invalid_primary_branch(
    monkeypatch: pytest.MonkeyPatch,
    primary_branch: object,
) -> None:
    with pytest.raises(ValueError, match='primary_branch'):
        _load_repo_config(monkeypatch, _create_config_data(primary_branch))


def test_repo_config_requires_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    config_data = _create_config_data()
    repositories = config_data['repositories']
    assert isinstance(repositories, dict)
    del repositories['branches']

    with pytest.raises(ValueError, match='branches'):
        _load_repo_config(monkeypatch, config_data)


def test_repo_config_requires_primary_branch_in_branch_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match='primary_branch release'):
        _load_repo_config(monkeypatch, _create_config_data('release'))


@pytest.mark.parametrize(
    ('branches', 'error_pattern'),
    [
        ({}, 'branches'),
        ({'develop': {'label': ''}}, '代码分支 develop'),
        ({'develop': {'label': '稳定分支', 'desc': 1}}, 'desc'),
    ],
)
def test_repo_config_rejects_invalid_branch_options(
    monkeypatch: pytest.MonkeyPatch,
    branches: object,
    error_pattern: str,
) -> None:
    with pytest.raises(ValueError, match=error_pattern):
        _load_repo_config(monkeypatch, _create_config_data(branches=branches))
