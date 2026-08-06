"""``current_instance_should_force_login`` 判定逻辑单测。

国服 / B服 / 国际服 是三个不同的游戏客户端，各自保留一套登录状态；
只有当一条龙中同客户端类型的实例多于一个时，才需要强制重新登录
以保证登录的是该实例配置的账号。
"""

import pytest

import one_dragon.base.config.one_dragon_config as od_config
from one_dragon.base.config.game_account_config import GameAccountConfig
from one_dragon.base.config.one_dragon_config import (
    InstanceRun,
    OneDragonConfig,
    OneDragonInstance,
)


class FakeGameAccountConfig:
    """按实例 idx 返回预设的客户端类型，隔离真实配置文件。"""

    clients: dict[int, str] = {}

    @classmethod
    def has_multi_instance_same_client(cls, current_idx: int, instance_indices: list[int]) -> bool:
        current_client = FakeGameAccountConfig.clients.get(current_idx, 'cn')
        client_count: dict[str, int] = {}
        for idx in instance_indices:
            client = FakeGameAccountConfig.clients.get(idx, 'cn')
            client_count[client] = client_count.get(client, 0) + 1
        return client_count.get(current_client, 0) > 1


def _build_cfg(
    monkeypatch: pytest.MonkeyPatch,
    clients: dict[int, str],
    active_idx: int,
    active_in_od_indices: list[int],
    instance_run: InstanceRun,
) -> OneDragonConfig:
    monkeypatch.setattr(od_config, 'GameAccountConfig', FakeGameAccountConfig)
    FakeGameAccountConfig.clients = clients
    monkeypatch.setattr(OneDragonConfig, 'instance_run', property(lambda self: instance_run.value.value))
    # 用 __new__ 构建空白对象，跳过 YamlConfig.__init__，避免读取真实工作目录的 one_dragon 配置
    cfg = OneDragonConfig.__new__(OneDragonConfig)
    cfg._temp_instance_indices = None
    cfg.instance_list = [
        OneDragonInstance(
            idx,
            f'实例{idx}',
            active=(idx == active_idx),
            active_in_od=(idx in active_in_od_indices),
        )
        for idx in clients
    ]
    return cfg


class TestGameClient:
    """``GameAccountConfig.game_client`` 归类：国服 / B服 / 国际服 三种客户端。"""

    @pytest.mark.parametrize('region, expected_client', [
        ('cn', 'cn'),
        ('cn_b', 'cnb'),
        ('twhkmo', 'intl'),
        ('asia', 'intl'),
        ('us', 'intl'),
        ('eu', 'intl'),
    ])
    def test_region_mapping(
        self,
        region: str,
        expected_client: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cfg = GameAccountConfig(99)
        monkeypatch.setattr(cfg, 'get', lambda key, default=None: region)
        assert cfg.game_client == expected_client


class TestCurrentInstanceShouldForceLogin:
    """``OneDragonConfig.current_instance_should_force_login`` 判定。"""

    def test_all_mode_same_client_multi_instances(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，同客户端（国际服）有多个实例 → 需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'cn', 2: 'intl', 3: 'intl'},
            active_idx=2,
            active_in_od_indices=[1, 2, 3],
            instance_run=InstanceRun.ALL,
        )
        assert cfg.current_instance_should_force_login is True

    def test_all_mode_sole_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，每个客户端类型都只有一个实例 → 不需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'cn', 2: 'intl'},
            active_idx=2,
            active_in_od_indices=[1, 2],
            instance_run=InstanceRun.ALL,
        )
        assert cfg.current_instance_should_force_login is False

    def test_all_mode_cross_client_trio(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，国服 / B服 / 国际服各一个实例 → 跨客户端类型不互相触发强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'cn', 2: 'cnb', 3: 'intl'},
            active_idx=2,
            active_in_od_indices=[1, 2, 3],
            instance_run=InstanceRun.ALL,
        )
        assert cfg.current_instance_should_force_login is False

    def test_all_mode_other_client_multi_current_sole(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，其他客户端类型有多个实例，当前客户端仅当前实例 → 不强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'cn', 2: 'cn', 3: 'intl'},
            active_idx=3,
            active_in_od_indices=[1, 2, 3],
            instance_run=InstanceRun.ALL,
        )
        assert cfg.current_instance_should_force_login is False

    def test_all_mode_same_client_not_in_od(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，同客户端类型有两个实例但其中一个不在一条龙中运行 → 不需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'intl', 2: 'intl'},
            active_idx=1,
            active_in_od_indices=[1],
            instance_run=InstanceRun.ALL,
        )
        assert cfg.current_instance_should_force_login is False

    def test_all_mode_temp_instances_multi_same_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，设置临时实例列表含两个同客户端实例（即使都未勾选在一条龙中运行）→ 需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'intl', 2: 'intl'},
            active_idx=1,
            active_in_od_indices=[],
            instance_run=InstanceRun.ALL,
        )
        cfg.set_temp_instance_indices([1, 2])
        assert cfg.current_instance_should_force_login is True

    def test_all_mode_temp_instances_only_current(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，临时实例列表只含当前实例 → 不需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'intl', 2: 'intl'},
            active_idx=1,
            active_in_od_indices=[1, 2],
            instance_run=InstanceRun.ALL,
        )
        cfg.set_temp_instance_indices([1])
        assert cfg.current_instance_should_force_login is False

    def test_all_mode_single_instance(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """全部实例模式，只有一个实例 → 不需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'intl'},
            active_idx=1,
            active_in_od_indices=[1],
            instance_run=InstanceRun.ALL,
        )
        assert cfg.current_instance_should_force_login is False

    def test_current_mode_multi_same_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """仅运行当前模式，即使同客户端有多个实例 → 不需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'intl', 2: 'intl'},
            active_idx=1,
            active_in_od_indices=[1, 2],
            instance_run=InstanceRun.CURRENT,
        )
        assert cfg.current_instance_should_force_login is False

    def test_no_active_instance(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """没有激活实例 → 不需要强制登录。"""
        cfg = _build_cfg(
            monkeypatch,
            clients={1: 'intl', 2: 'intl'},
            active_idx=-1,
            active_in_od_indices=[1, 2],
            instance_run=InstanceRun.ALL,
        )
        assert cfg.current_instance_should_force_login is False
