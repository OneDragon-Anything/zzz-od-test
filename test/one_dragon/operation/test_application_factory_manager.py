from pathlib import Path
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginSource


def _factory(
    app_id: str,
    default_group: bool,
    internal_app: bool,
    priority: int | None,
) -> MagicMock:
    factory = MagicMock()
    factory.app_id = app_id
    factory.default_group = default_group
    factory.internal_app = internal_app
    factory.priority = priority
    return factory


def test_discover_factories_returns_one_ordered_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认应用先按优先级排序，其他应用随后保留发现顺序。"""
    standalone = _factory('standalone', False, False, None)
    default_without_priority = _factory('default_z', True, False, None)
    internal = _factory('internal', False, True, None)
    default_later = _factory('default_b', True, False, 20)
    default_first = _factory('default_a', True, False, 10)
    discovered = [
        standalone,
        default_without_priority,
        internal,
        default_later,
        default_first,
    ]
    manager = ApplicationFactoryManager(
        MagicMock(),
        [(tmp_path, PluginSource.BUILTIN)],
    )
    monkeypatch.setattr(manager, '_scan_directory', lambda *_args: discovered)

    result = manager.discover_factories()

    assert [factory.app_id for factory in result] == [
        'default_a',
        'default_b',
        'default_z',
        'standalone',
        'internal',
    ]
