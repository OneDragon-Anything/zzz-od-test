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

覆盖 app config 分支(开关关 → ``round_success('未开启')``,守住下游 ``@node_from`` 匹配词契约):
- ``handle_auto_manage``(auto_manage_enabled=False)→ status=未开启自动托管(= ``handle_adventure_squad`` 的 ``@node_from`` 匹配词,关托管才走子玩法链)。
- ``handle_yum_cha_sin_submit``(yum_cha_sin=False)→ status=未开启(= ``handle_craft`` 的 ``@node_from`` 匹配词)。
- ``handle_good_goods`` / ``handle_boo_box``(默认关)→ status=未开启。

覆盖子 op 薄包装/混合节点分支(方法论范例,见 testing §3 动作一):
- ``click_squad_team``(混合:守卫 ``not self.claim`` + 薄包装 ocr)3 分支:claim=False→``跳过收获``(守卫)/claim=True+游历→``游历小队``(薄包装命中)/claim=True+制造坊→``未匹配到目标文本``(薄包装未命中 round_retry)。

未覆盖(留标记,见 `随便观.md` 备注):
- ``Transport`` / interact 狮耶 / move:run_operation Transport + controller interact(朝向 + 时机,手动难复现)。
- ``SuibianTempleAutoManage``(自动托管/经营日志画面无独立 screen_info,误匹配委托助手;且 ``check_and_stop_hosting`` 循环 click 停止托管/开始托管,单帧 mock 难覆盖完整停止→重启流程)。
- 经营总览(无 screen_info)。
- 各子 op 的操作 node(收获/派遣/制造/聘用 等,需多态 fixture + 中间状态)。

fixture(`screens/随便观/`):入口-手动态 / 入口-自动托管中 / 自动托管 / 游历 / 制造坊 / 售卖铺 /
饮茶仙 / 邦巢 / 德丰大押 / 好物铺 / 经营总览(11 张,实拍归档)。

注:各 ``goto_X`` 的 ``check_and_update_current_screen`` 命中对应 screen → ``round_success(status=screen_name)``。
"""
import pytest
from test.conftest import TestContext

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
from zzz_od.application.suibian_temple.suibian_temple_app import SuibianTempleApp
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig


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

    def test_click_squad_team_skip_claim(self, test_context: TestContext) -> None:
        """``click_squad_team``(混合节点:守卫+薄包装)claim=False → status=跳过收获(显式守卫分支,不需 mock)。

        混合节点范例:``if not self.claim: return round_success('跳过收获')`` 是显式守卫分支
        (动作一「混合」类:分支 = 显式 statuses ∪ helper 契约,别只数 helper 那部分)。
        """
        op = SuibianTempleAdventureSquad(test_context, claim=False, dispatch=False)
        result = op.click_squad_team()
        assert result.status == '跳过收获', 'claim=False 应走守卫分支直接跳过收获'

    def test_click_squad_team_hit(self, test_context: TestContext) -> None:
        """claim=True + 游历画面(OCR「游历小队」)→ ``click_squad_team`` 薄包装命中 → status=游历小队。

        薄包装命中分支范例:``return round_by_ocr_and_click_priority(['游历小队'])`` 命中 →
        ``round_success(status=匹配的 target)``。
        """
        self._mock(test_context, '游历')
        op = SuibianTempleAdventureSquad(test_context, claim=True, dispatch=False)
        op.screenshot()
        result = op.click_squad_team()
        assert result.is_success, '游历画面应 OCR 到「游历小队」并点击 → round_success'
        assert result.status == '游历小队'

    def test_click_squad_team_miss(self, test_context: TestContext) -> None:
        """claim=True + 制造坊(无「游历小队」)→ ``click_squad_team`` 薄包装未命中 → round_retry。

        薄包装不命中分支范例(现有测试多只测命中,此为补充):OCR 找不到 target →
        ``round_retry('未匹配到目标文本')``,``is_success=False``。

        注:不能用「入口」做未命中 mock —— 入口右侧「游历」tab 文字与 target「游历小队」
        LCS 误匹配会命中(印证方法论「mock 哪帧先读 node + 注意 LCS 误匹配」)。
        """
        self._mock(test_context, '制造坊')
        op = SuibianTempleAdventureSquad(test_context, claim=True, dispatch=False)
        op.screenshot()
        result = op.click_squad_team()
        assert not result.is_success, '制造坊无「游历小队」应 round_retry(未命中)'
        assert result.status == '未匹配到目标文本'

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

    def test_handle_auto_manage_disabled(
        self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auto_manage_enabled=False → handle_auto_manage → status=未开启自动托管(不跑 SuibianTempleAutoManage)。

        该 status 是 ``handle_adventure_squad`` 的 ``@node_from(from_name='处理自动托管',
        status='未开启自动托管')`` 匹配词 —— 关托管才走游历/制造等子玩法链。monkeypatch 改 config
        属性(不写盘、自动还原),守住该编排边契约。
        """
        monkeypatch.setattr(SuibianTempleConfig, 'auto_manage_enabled', False)
        app = SuibianTempleApp(test_context)
        result = app.handle_auto_manage()
        assert result.status == '未开启自动托管', '关托管应跳过 SuibianTempleAutoManage 直接返回'

    def test_handle_yum_cha_sin_disabled(
        self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """yum_cha_sin=False → handle_yum_cha_sin_submit → status=未开启。

        该 status 是 ``handle_craft`` 的 ``@node_from(from_name='处理饮茶仙', status='未开启')``
        匹配词 —— 关饮茶仙则饮茶仙后直接进制造坊(不经「饮茶仙后处理游历」)。
        """
        monkeypatch.setattr(SuibianTempleConfig, 'yum_cha_sin', False)
        app = SuibianTempleApp(test_context)
        result = app.handle_yum_cha_sin_submit()
        assert result.status == '未开启', '关饮茶仙应跳过 SuibianTempleYumChaSin 直接返回'

    def test_handle_good_goods_disabled(
        self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """good_goods_purchase_enabled=False(默认)→ handle_good_goods → status=未开启。"""
        monkeypatch.setattr(SuibianTempleConfig, 'good_goods_purchase_enabled', False)
        app = SuibianTempleApp(test_context)
        result = app.handle_good_goods()
        assert result.status == '未开启', '关好物铺购买应跳过 SuibianTempleGoodGoods 直接返回'

    def test_handle_boo_box_disabled(
        self, test_context: TestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """boo_box_purchase_enabled=False(默认)→ handle_boo_box → status=未开启。"""
        monkeypatch.setattr(SuibianTempleConfig, 'boo_box_purchase_enabled', False)
        app = SuibianTempleApp(test_context)
        result = app.handle_boo_box()
        assert result.status == '未开启', '关邦巢购买应跳过 SuibianTempleBooBox 直接返回'
