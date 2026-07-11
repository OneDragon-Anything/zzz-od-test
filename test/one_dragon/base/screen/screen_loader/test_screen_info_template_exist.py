from test.conftest import TestContext


class TestScreenInfoTemplateExist:
    """screen_info template area 完整性:遍历所有画面 × 所有 template area,断言模板都能读到。

    覆盖 hollow / lost_void / menu / enter_game 等各玩法画面引用的 template(它们的
    ``template_sub_dir`` 跨整个 ``assets/template/``)。证明「被画面引用的模板都存在且能读」。
    """

    def test_screen_info_template(self, test_context: TestContext):
        missing = []
        for screen_info in test_context.screen_loader.screen_info_list:
            for area in screen_info.area_list:
                if not area.is_template_area or not area.template_sub_dir:
                    continue
                template = test_context.template_loader.get_template(
                    area.template_sub_dir, area.template_id,
                )
                if template is None or template.raw is None:
                    missing.append(
                        f'{screen_info.screen_name}/{area.area_name} → '
                        f'{area.template_sub_dir}/{area.template_id}'
                    )
        assert not missing, f'缺失画面模板: {missing}'
