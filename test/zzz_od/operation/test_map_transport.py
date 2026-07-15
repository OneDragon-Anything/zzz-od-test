"""MapTransport 地图传送 op 测试(用实拍 fixture)。

覆盖 MapTransport 节点(`src/zzz_od/operation/map_transport.py`):
- ``choose_tp``(选传送点):澄辉坪传送点列表 → OCR 找随便观点 → click。
- ``click_tp``(传送确认弹窗):点 ``地图/确认`` area → success。

fixture(`screens/地图/`):选传送点 / 传送确认弹窗(2026-07-15 实拍,网格/列表传送视图,`map.yml`)。

未覆盖:
- ``choose_area``:选区域(OCR 找区域名 + drag 地图翻页),需默认态 fixture + drag 逻辑复杂。
"""
from test.conftest import TestContext

from zzz_od.operation.map_transport import MapTransport


class TestMapTransport:
    """地图传送 op 测试。"""

    def _make_op(self, test_context: TestContext, state: str) -> MapTransport:
        test_context.mock_screen('地图', state)
        op = MapTransport(test_context, '澄辉坪', '随便观')
        op.screenshot()
        return op

    def test_choose_tp(self, test_context: TestContext) -> None:
        """选传送点列表(澄辉坪,有「随便观」)→ choose_tp OCR 找并点 → success。

        ``choose_tp`` 在传送点列表 OCR 找 ``tp_name``(随便观),命中则 click。
        """
        op = self._make_op(test_context, '选传送点')
        result = op.choose_tp()
        assert result.is_success, '应找到「随便观」传送点并点击'

    def test_click_tp(self, test_context: TestContext) -> None:
        """传送确认弹窗 → click_tp 点 ``地图/确认`` area → success。

        ``click_tp`` = ``round_by_find_and_click_area('地图', '确认')``,点确认 area(@1024,600-1232,708)。
        """
        op = self._make_op(test_context, '传送确认弹窗')
        result = op.click_tp()
        assert result.is_success, '应点 地图/确认 area'
