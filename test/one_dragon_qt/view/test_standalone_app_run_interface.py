import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from one_dragon_qt.view.standalone_app_run_interface import StandaloneRunInterface


def test_get_all_apps_uses_standalone_apps() -> None:
    run_context = MagicMock()
    run_context.standalone_apps = ['default_app', 'standalone_app']
    run_context.get_application_name.side_effect = {
        'default_app': '默认应用',
        'standalone_app': '独立应用',
    }.get
    interface = SimpleNamespace(ctx=SimpleNamespace(run_context=run_context))

    result = StandaloneRunInterface._get_all_apps(interface)

    assert result == {
        'default_app': '默认应用',
        'standalone_app': '独立应用',
    }


def test_save_visible_app_list_preserves_filtered_ids_in_place() -> None:
    config = SimpleNamespace(
        app_list=[
            'default_app',
            'internal_app',
            'standalone_app',
            'missing_app',
        ],
    )
    interface = SimpleNamespace(
        ctx=SimpleNamespace(standalone_app_config=config),
        _get_all_apps=lambda: {
            'default_app': '默认应用',
            'standalone_app': '独立应用',
            'new_app': '新应用',
        },
    )

    StandaloneRunInterface._save_visible_app_list(
        interface,
        ['standalone_app', 'new_app'],
    )

    assert config.app_list == [
        'standalone_app',
        'internal_app',
        'new_app',
        'missing_app',
    ]


def test_refresh_filters_runtime_view_without_rewriting_saved_ids() -> None:
    config = SimpleNamespace(
        app_list=['standalone_app', 'internal_app', 'missing_app'],
        active_app_id='internal_app',
    )
    app_list_widget = MagicMock()
    interface = SimpleNamespace(
        ctx=SimpleNamespace(standalone_app_config=config),
        app_list_widget=app_list_widget,
        app_id='',
        _get_all_apps=lambda: {'standalone_app': '独立应用'},
        _update_setting_btn_visibility=MagicMock(),
    )

    StandaloneRunInterface._refresh_app_list(interface)

    app_list_widget.set_app_list.assert_called_once_with([
        ('standalone_app', '独立应用'),
    ])
    app_list_widget.select_app.assert_called_once_with('standalone_app')
    assert interface.app_id == 'standalone_app'
    assert config.app_list == ['standalone_app', 'internal_app', 'missing_app']
    assert config.active_app_id == 'internal_app'
