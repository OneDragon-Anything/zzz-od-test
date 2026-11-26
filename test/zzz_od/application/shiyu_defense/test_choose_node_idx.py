import pytest
from test.conftest import TestContext

from zzz_od.application.shiyu_defense.shiyu_defense_app import ShiyuDefenseApp


class TestChooseNodeIdx:

    def test_parse_connected_progress(self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """OCR 将 2/5 连写为 215 时，应选择第 3 节。"""
        monkeypatch.setattr(
            test_context.ocr,
            'crop_and_run_ocr',
            lambda _screen, _rect: {'215': {}},
        )
        app = ShiyuDefenseApp(test_context)
        clicked_area_names: list[str] = []

        def mock_find_and_click_area(
                _screen: object, _screen_name: str, area_name: str
        ) -> object:
            clicked_area_names.append(area_name)
            return app.round_success(area_name)

        monkeypatch.setattr(app, 'round_by_find_and_click_area', mock_find_and_click_area)

        result = app.choose_node_idx()

        assert result.status == '节点-03'
        assert app.config.critical_max_node_idx == 5
        assert app.current_node_idx == 3
        assert clicked_area_names == ['节点-03']
