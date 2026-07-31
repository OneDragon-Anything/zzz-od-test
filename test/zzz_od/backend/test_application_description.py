"""application description(backend 反射 factory 模块的 Application 子类 docstring)契约 + 取数测试。"""
from test.conftest import TestContext

from zzz_od.backend.app_registry import _app_description
from zzz_od.backend.schemas import ApplicationInfo


def test_get_application_description_returns_class_docstring(test_context: TestContext) -> None:
    """charge_plan factory 模块能扫到 ChargePlanApp → _app_description 返回非空、含关键语义。"""
    factory = test_context.run_context._application_factory_map['charge_plan']
    desc = _app_description(factory)
    assert isinstance(desc, str)
    assert desc, 'charge_plan description 为空(factory 模块未 import App 类或类无 docstring?)'
    assert '体力' in desc  # D4 约定:有消耗必标,charge_plan 消耗体力


def test_application_info_has_description_field() -> None:
    """ApplicationInfo dataclass 含 description 字段(默认空串)。"""
    info = ApplicationInfo(app_id='x', app_name='名')
    assert hasattr(info, 'description')
    assert info.description == ''


def test_all_registered_apps_have_class_docstring(test_context: TestContext) -> None:
    """契约:每个注册 app 的 factory 模块都能反射到恰好一个非空 docstring 的 Application 子类。

    防止 app 补描述后回退腐烂。源码盲受众靠这个 description 选 app。
    """
    factory_map = test_context.run_context._application_factory_map
    assert factory_map, '未注册任何 app factory(扫描没跑?)'

    empty_doc: list[str] = []
    for app_id, factory in factory_map.items():
        desc = _app_description(factory)
        if not desc:
            empty_doc.append(app_id)

    assert not empty_doc, f'app 经 backend 反射未取到非空 description: {empty_doc}'
