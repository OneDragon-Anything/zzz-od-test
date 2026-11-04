"""真实工厂、原生副本计划与离屏设置检查；不创建游戏控制器。"""
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

os.environ['QT_QPA_PLATFORM'] = 'offscreen'


class NativeRegistrationTests(unittest.TestCase):
    def test_discovery_routes_and_settings_without_game_input(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from one_dragon.utils import os_utils
        from zzz_od.context.zzz_context import ZContext
        from one_dragon_qt.services.app_setting.app_setting_manager import AppSettingManager
        from zzz_od.application.inventory_maintain.inventory_maintain import (
            ROOT, ROUTES, StockStore, build_plan, EphemeralChargePlan,
            ContextProxy, native_battle,
        )
        from zzz_od.application.inventory_maintain.inventory_maintain_settings import InventoryMaintainSettings
        from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium

        checkout = Path(__file__).resolve().parents[4]
        os_utils.set_work_dir(checkout)
        app = QApplication.instance() or QApplication([])
        ctx = ZContext()
        ctx.register_application_factory()
        ctx.compendium_service.reload()
        for app_id in ('inventory_inspection', 'inventory_maintain'):
            self.assertIn(app_id, ctx.run_context.standalone_app_ids)
            self.assertNotIn(app_id, ctx.run_context.default_group_apps)
            factory = ctx.run_context._application_factory_map[app_id]
            self.assertFalse(factory.need_notify)
            task = factory.create_application(ctx.current_instance_idx, 'test')
            self.assertIsNone(task.run_record)
        manager = AppSettingManager(ctx)
        manager.discover()
        self.assertIn('inventory_maintain', manager.settable_app_ids)
        self.assertEqual(len(ROUTES), 97)
        for route in ROUTES.values():
            plan = build_plan(ctx, route)
            config = EphemeralChargePlan(plan)
            proxy = ContextProxy(ctx, config)
            combat = native_battle(proxy, plan, route, lambda: None, lambda: None)
            combat._init_network()
            TransportByCompendium(proxy, '训练', route.get('category', '实战模拟室'), route['type'])
            self.assertEqual(plan.plan_times, 1)
            self.assertEqual(plan.run_times, 0)
            self.assertFalse(config.is_restore_charge_enabled)
            self.assertIsNone(ctx.controller)

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'config', root / 'config')
            gui_ctx = SimpleNamespace(current_instance_idx=0, run_context=SimpleNamespace(is_context_stop=True))
            view = InventoryMaintainSettings(gui_ctx, 'test', root=root)
            view.init_config()
            self.assertEqual(view.material.count(), 97)
            self.assertTrue(view.save_button.isEnabled())
            view.material.setCurrentIndex(0)
            view.add_material()
            view.target.setValue(31)
            view.material.setCurrentIndex(1)
            view.add_material()
            view.target.setValue(42)
            item = view.items.takeItem(1)
            view.items.insertItem(0, item)
            view.save_targets()
            saved = StockStore(0, root).read()
            self.assertEqual([row['target'] for row in saved['targets']], [42, 31])
            view.init_config()
            self.assertEqual(view.items.item(0).data(Qt.ItemDataRole.UserRole)['target'], 42)
            gui_ctx.current_instance_idx = 1
            view.save_targets()
            self.assertEqual(StockStore(0, root).read(), saved)
            gui_ctx.current_instance_idx = 0
            gui_ctx.run_context.is_context_stop = False
            view.init_config()
            self.assertFalse(view.save_button.isEnabled())
            view.deleteLater()
            app.processEvents()
        self.assertIsNone(ctx.controller)


if __name__ == '__main__':
    unittest.main()
