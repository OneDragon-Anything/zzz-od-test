"""application description(class docstring 来源)契约 + 取数测试。"""
from test.conftest import TestContext


def test_get_application_description_returns_class_docstring(test_context: TestContext) -> None:
    """charge_plan factory 设了 app_class + 类有 docstring → get_application_description 返回非空、含关键语义。"""
    desc = test_context.run_context.get_application_description('charge_plan')
    assert isinstance(desc, str)
    assert desc, 'charge_plan description 为空(factory 未设 app_class 或类无 docstring?)'
    assert '体力' in desc  # D4 约定:有消耗必标,charge_plan 消耗体力
