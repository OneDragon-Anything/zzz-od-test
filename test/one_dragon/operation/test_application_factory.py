from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_run_record import AppRunRecord


def _app_const(default_group: object, internal_app: object | None = None) -> ModuleType:
    app_const = ModuleType('test_app_const')
    app_const.APP_ID = 'test_app'
    app_const.APP_NAME = '测试应用'
    app_const.DEFAULT_GROUP = default_group
    app_const.NEED_NOTIFY = False
    if internal_app is not None:
        app_const.INTERNAL_APP = internal_app
    return app_const


def test_missing_internal_app_defaults_to_false() -> None:
    """旧 const 缺少 INTERNAL_APP 时应映射为 standalone 能力。"""
    factory = ApplicationFactory(_app_const(default_group=False))

    assert factory.default_group is False
    assert factory.internal_app is False


@pytest.mark.parametrize(
    ('default_group', 'internal_app'),
    [
        (True, False),
        (False, False),
        (False, True),
    ],
)
def test_legal_application_entry_combinations(
    default_group: bool,
    internal_app: bool,
) -> None:
    factory = ApplicationFactory(_app_const(default_group, internal_app))

    assert factory.default_group is default_group
    assert factory.internal_app is internal_app


def test_default_group_and_internal_app_cannot_both_be_true() -> None:
    with pytest.raises(ValueError, match='不能同时为 True'):
        ApplicationFactory(_app_const(default_group=True, internal_app=True))


@pytest.mark.parametrize(
    ('default_group', 'internal_app', 'error_field'),
    [
        ('yes', False, 'DEFAULT_GROUP'),
        (False, 'yes', 'INTERNAL_APP'),
    ],
)
def test_application_entry_fields_must_be_boolean(
    default_group: object,
    internal_app: object,
    error_field: str,
) -> None:
    with pytest.raises(ValueError, match=error_field):
        ApplicationFactory(_app_const(default_group, internal_app))


def test_default_run_record_uses_current_server_refresh_offset_and_cache() -> None:
    factory = ApplicationFactory(_app_const(default_group=False))
    factory.ctx = MagicMock()
    factory.ctx.game_account_config.game_refresh_hour_offset = 4

    with patch(
        'one_dragon.base.operation.application.application_factory.AppRunRecord'
    ) as record_cls:
        first = factory.get_run_record(instance_idx=2)
        second = factory.get_run_record(instance_idx=2)

    assert first is record_cls.return_value
    assert second is first
    record_cls.assert_called_once_with(
        app_id='test_app',
        instance_idx=2,
        game_refresh_hour_offset=4,
    )


def test_custom_run_record_override_is_still_cached() -> None:
    custom_record = MagicMock(spec=AppRunRecord)
    create_calls: list[int] = []

    class CustomRecordFactory(ApplicationFactory):
        def create_run_record(self, instance_idx: int) -> AppRunRecord:
            create_calls.append(instance_idx)
            return custom_record

    factory = CustomRecordFactory(_app_const(default_group=False))

    assert factory.get_run_record(instance_idx=3) is custom_record
    assert factory.get_run_record(instance_idx=3) is custom_record
    assert create_calls == [3]
