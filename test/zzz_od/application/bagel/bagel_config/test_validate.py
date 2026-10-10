import pytest

from zzz_od.application.bagel.bagel_config import BagelConfig


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        *[('sell_interval', value) for value in (0, 1000, True, 1.5, '2', None)],
        ('max_failure_retries', -1),
        ('max_failure_retries', 101),
        ('max_failure_retries', True),
        ('max_failure_retries', 1.5),
        ('max_failure_retries', '5'),
        ('max_success_rounds', -1),
        ('max_success_rounds', 1001),
        ('max_success_rounds', True),
        ('max_success_rounds', 1.5),
        ('max_success_rounds', '0'),
        ('clean_mode', 'unknown'),
        ('clean_types', ['全部']),
        ('clean_types', ['贵重物品', '贵重物品']),
        ('clean_qualities', ['SS']),
        ('clean_qualities', 'S'),
        ('auto_clean_warehouse', 1),
        ('auto_clean_warehouse', 'true'),
    ],
)
def test_manual_yaml_invalid_values(
    config: BagelConfig, field: str, value: object
) -> None:
    """绕过 setter 手改 YAML 的值也必须被启动校验拒绝。"""
    config.data[field] = value
    with pytest.raises(ValueError):
        config.validate()


@pytest.mark.parametrize('limit', [0, 1, 1000])
def test_valid_success_limit(config: BagelConfig, limit: int) -> None:
    """0 不限制成功次数，其余边界保留。"""
    config.max_success_rounds = limit
    config.validate()
    assert BagelConfig(99, 'standalone').max_success_rounds == limit


@pytest.mark.parametrize('limit', [-1, 1001, True, 1.5, '0'])
def test_invalid_success_limit_setter(config: BagelConfig, limit: object) -> None:
    """编辑配置时立即拒绝越界与非整数。"""
    with pytest.raises(ValueError, match='0 至 1000'):
        config.max_success_rounds = limit


def test_legacy_targets_text_is_not_read_or_rewritten(config: BagelConfig) -> None:
    """旧名单即使损坏也不参与新配置，且不迁移用户文件。"""
    config.data['targets_text'] = ['旧名单内容']
    config.validate()
    assert config.data['targets_text'] == ['旧名单内容']


@pytest.mark.parametrize('limit', [0, 1, 5, 100])
def test_failure_retries_persist(config: BagelConfig, limit: int) -> None:
    """额外入场额度按整数范围保存，旧配置缺省为五。"""
    config.max_failure_retries = limit
    config.validate()
    assert BagelConfig(99, 'standalone').max_failure_retries == limit


@pytest.mark.parametrize('limit', [-1, 101, True, 1.5, '5', None])
def test_invalid_failure_retries_setter(config: BagelConfig, limit: object) -> None:
    """保存前拒绝越界、布尔值和非整数。"""
    with pytest.raises(ValueError, match='0 至 100'):
        config.max_failure_retries = limit


def test_auto_clean_warehouse_defaults_on() -> None:
    """仓库清理开关默认打开。"""
    assert BagelConfig(99, 'standalone').auto_clean_warehouse is True


def test_default_clean_selection_preserves_old_behavior(config: BagelConfig) -> None:
    """旧配置不用补字段，仍只卖三种类型与 C 到 S。"""
    assert config.max_failure_retries == 5
    assert config.max_success_rounds == 1
    assert config.clean_mode == 'default'
    assert config.clean_filter_areas() == (
        '筛选-贵重物品', '筛选-战术棱镜', '筛选-其他',
        '筛选-C', '筛选-B', '筛选-A', '筛选-S',
    )


def test_custom_clean_requires_both_groups_when_enabled(config: BagelConfig) -> None:
    """仅启用自定义出售时要求类型、品质均有选择。"""
    config.clean_mode = 'custom'
    with pytest.raises(ValueError, match='同时选择'):
        config.validate()
    config.clean_types = ['装备', '门禁卡']
    with pytest.raises(ValueError, match='同时选择'):
        config.validate()
    config.clean_qualities = ['Z']
    config.validate()
    assert config.clean_filter_areas() == ('筛选-装备', '筛选-门禁卡', '筛选-Z')
    config.auto_clean_warehouse = False
    config.clean_types = []
    config.validate()
