"""SuibianTempleApp 随便观测试。

覆盖各子 op 的 start node(mock 对应子画面 fixture,断言识别 / 点击):
- ``check_initial_screen``(随便观-入口,手动态):识别入口 → status=随便观-入口。
- ``SuibianTempleAdventureSquad.goto_adventure``(随便观-入口):click ``按钮-游历``。
- ``SuibianTempleCraft.goto_craft``(随便观-制造坊):status=随便观-制造坊。
- ``SuibianTempleSalesStall.goto_sales_stall``(随便观-售卖铺):status=随便观-售卖铺。
- ``SuibianTempleYumChaSin.goto_yum_cha_sin``(随便观-饮茶仙):status=随便观-饮茶仙。
- ``SuibianTempleBooBox.goto_boo_box``(随便观-邦巢):status=随便观-邦巢。
- ``SuibianTempleGoodGoods.goto_linli_jiefang``(好物铺,已在邻里街坊):OCR「好物铺」→ status=已在邻里街坊-进入好物铺。
- ``handle_pawnshop``:德丰大押代码未开启 → status=未开启(不需 mock)。

未覆盖(留标记,见 `随便观.md` 备注):
- ``Transport`` / interact 狮耶 / move:run_operation Transport + controller interact(朝向 + 时机,手动难复现)。
- ``SuibianTempleAutoManage``(自动托管/经营日志画面无独立 screen_info,误匹配委托助手;且 ``check_and_stop_hosting`` 循环 click 停止托管/开始托管,单帧 mock 难覆盖完整停止→重启流程)。
- 经营总览(无 screen_info)。
- 各子 op 的操作 node(收获/派遣/制造/聘用 等,需多态 fixture + 中间状态)。

fixture(`screens/随便观/`):入口-手动态 / 入口-自动托管中 / 自动托管 / 游历 / 制造坊 / 售卖铺 /
饮茶仙 / 邦巢 / 德丰大押 / 好物铺 / 经营总览(11 张,实拍归档)。

注:各 ``goto_X`` 的 ``check_and_update_current_screen`` 命中对应 screen → ``round_success(status=screen_name)``。
"""
from test.conftest import TestContext
from zzz_od.application.suibian_temple.suibian_temple_app import SuibianTempleApp
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_squad import (
    SuibianTempleAdventureSquad,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_boo_box import (
    SuibianTempleBooBox,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_craft import (
    SuibianTempleCraft,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_good_goods import (
    SuibianTempleGoodGoods,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_sales_stall import (
    SuibianTempleSalesStall,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_yum_cha_sin import (
    SuibianTempleYumChaSin,
)


class TestSuibianTempleApp:
    """随便观 app 测试。"""

    def _mock(self, test_context: TestContext, state: str) -> None:
        """读 ``screens/随便观/<state>.webp`` 设为 controller 下一帧。"""
        test_context.mock_screen('随便观', state)

    def test_check_initial_screen_in_temple(self, test_context: TestContext) -> None:
        """随便观-入口(手动态)→ check_initial_screen → status=随便观-入口。"""
        self._mock(test_context, '入口-手动态')
        app = SuibianTempleApp(test_context)
        app.screenshot()
        result = app.check_initial_screen()
        assert result.status == '随便观-入口', '应识别已在随便观-入口'

    def test_goto_adventure(self, test_context: TestContext) -> None:
        """随便观-入口 → click 按钮-游历 → 进游历画面(``until_not_find_all`` 两轮验证)。

        ``goto_adventure`` 用 ``round_by_find_and_click_area`` + ``until_not_find_all``
        (click 后等画面变游历、按钮-游历消失)。``until`` 用 ``last_screenshot`` 验证 +
        ``node_clicked`` 标志,需**两轮** —— 同一 op 实例手动连续调 ``goto_adventure``(不经 runner,
        ``node_clicked`` 保持,``_reset_status_for_new_node`` 只在 runner 进新 node 时才 reset):
        - 第 1 轮(``node_clicked=False``):mock 入口-手动态 → click 按钮-游历 → ``round_wait``。
        - 第 2 轮(``node_clicked=True``):mock 游历 → ``until`` 验证 按钮-游历 消失 → ``round_success``。
        """
        op = SuibianTempleAdventureSquad(test_context)
        # 第 1 轮:入口-手动态 → click 按钮-游历
        self._mock(test_context, '入口-手动态')
        op.screenshot()
        result1 = op.goto_adventure()
        assert result1.status == '按钮-游历', '第 1 轮应识别 按钮-游历 并 click(round_wait)'
        # 第 2 轮:游历画面 → 按钮-游历消失 → round_success
        self._mock(test_context, '游历')
        op.screenshot()
        result2 = op.goto_adventure()
        assert result2.is_success, 'click 后进游历画面,按钮-游历消失,应 round_success'

    def test_goto_craft(self, test_context: TestContext) -> None:
        """随便观-制造坊 → craft goto_craft → status=随便观-制造坊。"""
        self._mock(test_context, '制造坊')
        op = SuibianTempleCraft(test_context)
        op.screenshot()
        result = op.goto_craft()
        assert result.status == '随便观-制造坊', '应识别已在随便观-制造坊'

    def test_goto_sales_stall(self, test_context: TestContext) -> None:
        """随便观-售卖铺 → sales_stall goto_sales_stall → status=随便观-售卖铺。"""
        self._mock(test_context, '售卖铺')
        op = SuibianTempleSalesStall(test_context)
        op.screenshot()
        result = op.goto_sales_stall()
        assert result.status == '随便观-售卖铺', '应识别已在随便观-售卖铺'

    def test_goto_yum_cha_sin(self, test_context: TestContext) -> None:
        """随便观-饮茶仙 → yum_cha_sin goto_yum_cha_sin → status=随便观-饮茶仙。"""
        self._mock(test_context, '饮茶仙')
        op = SuibianTempleYumChaSin(test_context)
        op.screenshot()
        result = op.goto_yum_cha_sin()
        assert result.status == '随便观-饮茶仙', '应识别已在随便观-饮茶仙'

    def test_goto_boo_box(self, test_context: TestContext) -> None:
        """随便观-邦巢 → boo_box goto_boo_box → status=随便观-邦巢。"""
        self._mock(test_context, '邦巢')
        op = SuibianTempleBooBox(test_context)
        op.screenshot()
        result = op.goto_boo_box()
        assert result.status == '随便观-邦巢', '应识别已在随便观-邦巢'

    def test_goto_good_goods_click_linli(self, test_context: TestContext) -> None:
        """入口(手动态,OCR「邻里街坊」)→ good_goods goto_linli_jiefang → click 邻里街坊 → round_wait。"""
        self._mock(test_context, '入口-手动态')
        op = SuibianTempleGoodGoods(test_context)
        op.screenshot()
        result = op.goto_linli_jiefang()
        assert result.status == '邻里街坊', '入口应识别 邻里街坊 并点击'

    def test_goto_good_goods_in_menu(self, test_context: TestContext) -> None:
        """邻里街坊菜单(OCR「好物铺」选项)→ good_goods goto_linli_jiefang → round_success(已在邻里街坊-进入好物铺)。

        注:「好物铺」检测的是邻里街坊**菜单的选项文字**(普通文字,OCR 可识),不是好物铺画面的
        艺术字标题 logo(那个 OCR 只识出「铺」单字)。app 靠菜单选项,不靠画面标题。
        """
        self._mock(test_context, '邻里街坊菜单')
        op = SuibianTempleGoodGoods(test_context)
        op.screenshot()
        result = op.goto_linli_jiefang()
        assert result.is_success, '邻里街坊菜单应 OCR 到「好物铺」选项 → round_success'
        assert result.status == '已在邻里街坊-进入好物铺'

    def test_handle_pawnshop_disabled(self, test_context: TestContext) -> None:
        """德丰大押代码未开启 → handle_pawnshop → status=未开启(不需 mock)。"""
        app = SuibianTempleApp(test_context)
        result = app.handle_pawnshop()
        assert result.status == '未开启', '德丰大押代码未开启,应直接返回未开启'
