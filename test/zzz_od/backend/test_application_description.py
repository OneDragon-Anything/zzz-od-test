"""application description(class docstring 来源)契约 + 取数测试。"""
from test.conftest import TestContext

from zzz_od.backend.schemas import ApplicationInfo


def test_get_application_description_returns_class_docstring(test_context: TestContext) -> None:
    """charge_plan factory 设了 app_class + 类有 docstring → get_application_description 返回非空、含关键语义。"""
    desc = test_context.run_context.get_application_description('charge_plan')
    assert isinstance(desc, str)
    assert desc, 'charge_plan description 为空(factory 未设 app_class 或类无 docstring?)'
    assert '体力' in desc  # D4 约定:有消耗必标,charge_plan 消耗体力


def test_application_info_has_description_field() -> None:
    """ApplicationInfo dataclass 含 description 字段(默认空串)。"""
    info = ApplicationInfo(app_id='x', app_name='名')
    assert hasattr(info, 'description')
    assert info.description == ''


def test_all_registered_apps_have_class_docstring(test_context: TestContext) -> None:
    """契约:每个注册 app 的 factory 都设了 app_class,且 app 类有非空 class docstring。

    防止 app 补描述后回退腐烂。源码盲受众靠这个 description 选 app。
    """
    factory_map = test_context.run_context._application_factory_map
    assert factory_map, '未注册任何 app factory(扫描没跑?)'

    missing_class: list[str] = []
    empty_doc: list[str] = []
    for app_id, factory in factory_map.items():
        if factory.app_class is None:
            missing_class.append(app_id)
            continue
        if not (factory.app_class.__doc__ or '').strip():
            empty_doc.append(app_id)

    assert not missing_class, f'factory 未设 app_class(漏配): {missing_class}'
    assert not empty_doc, f'app 类缺 class docstring: {empty_doc}'
