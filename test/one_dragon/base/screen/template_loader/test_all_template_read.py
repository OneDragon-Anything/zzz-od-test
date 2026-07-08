from test.conftest import TestContext


class TestAllTemplateRead:
    """磁盘模板兜底:遍历 ``assets/template/`` 所有模板,断言每个 ``raw`` 都能读。

    与配置引用维度(Agent / screen_info / 大地图)互补 —— 这是从磁盘侧证明
    「每个实际存在的模板都能被上层读到」,可发现「磁盘有模板但 raw.png 缺 / 读不了」的损坏。
    """

    def test_all_template_raw(self, test_context: TestContext):
        templates = test_context.template_loader.get_all_template_info_from_disk(need_raw=True)
        assert templates, '未扫到任何模板(assets/template 目录结构变了?)'
        missing = [f'{t.sub_dir}/{t.template_id}' for t in templates if t.raw is None]
        assert not missing, f'模板 raw 读失败: {missing}'
