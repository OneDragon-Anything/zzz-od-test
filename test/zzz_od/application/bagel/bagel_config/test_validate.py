import pytest

from zzz_od.application.bagel.bagel_config import BagelConfig


@pytest.mark.parametrize(
    'field,value',
    [
        ('sell_interval', 0),
        ('sell_interval', 1000),
        ('sell_interval', True),
        ('max_failure_retries', -1),
        ('max_failure_retries', 101),
        ('max_success_rounds', -1),
        ('max_success_rounds', 1001),
        ('clean_mode', 'unknown'),
        ('clean_types', ['全部']),
        ('clean_types', ['贵重物品', '贵重物品']),
        ('clean_qualities', ['SS']),
        ('auto_clean_warehouse', 1),
    ],
)
def test_manual_yaml_invalid_values(
    config: BagelConfig, field: str, value: object
) -> None:
    """绕过 setter 手改 YAML 的值也必须被启动校验拒绝。"""
    config.data[field] = value
    with pytest.raises(ValueError):
        config.validate()


@pytest.mark.parametrize(
    'limit',
    [
        0,
        1000,
    ],
)
def test_valid_success_limit(config: BagelConfig, limit: int) -> None:
    """0 不限制成功次数，其余边界保留。"""
    config.max_success_rounds = limit
    config.validate()
    assert BagelConfig(99, 'standalone').max_success_rounds == limit


@pytest.mark.parametrize(
    'limit',
    [
        True,
    ],
)
def test_invalid_success_limit_setter(config: BagelConfig, limit: object) -> None:
    """编辑配置时立即拒绝越界与非整数。"""
    with pytest.raises(ValueError, match='0 至 1000'):
        config.max_success_rounds = limit


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
