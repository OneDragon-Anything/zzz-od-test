from zzz_od.application.inventory_maintain import inventory_maintain as stock
ROOT = stock.ROOT
'ZZZ native adapter boundaries, no game input or battery consumption.'
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

class StockTests(unittest.TestCase):

    def test_two_runners_cannot_replace_or_clear_other_pending(self):
        first = stock.pending_journal(self.store)
        second = stock.pending_journal(stock.StockStore(0, self.temp.name))
        first({'pending': True, 'cost': 20})
        owned = self.store.read()['pending']
        with self.assertRaises(RuntimeError):
            second({'pending': True, 'cost': 20})
        with self.assertRaises(RuntimeError):
            second({})
        with self.assertRaises(RuntimeError):
            self.store.update('pending', {}, expected_pending={'wrong': True})
        self.assertEqual(self.store.read()['pending'], owned)
        first({})
        self.assertEqual(self.store.read()['pending'], {})

    def test_new_journal_cannot_clear_replaced_transaction(self):
        journal = stock.pending_journal(self.store)
        journal({'pending': True})
        saved = self.store.read()
        saved['pending']['transaction_id'] = 'someone-else'
        self.store.path.write_text(json.dumps(saved), encoding='utf-8')
        with self.assertRaises(RuntimeError):
            journal({})
        self.assertEqual(self.store.read()['pending']['transaction_id'], 'someone-else')

    def test_unavailable_catalog_entries_cannot_become_targets_or_infer_zero(self):
        scope = stock.unavailable_materials()
        self.assertEqual((scope['catalog_items'], scope['available_items']), (98, 97))
        self.assertEqual([row['id'] for row in scope['missing']], ['hamster-cage-pass'])
        self.assertTrue(all((row['target'] is None and row['quantity'] is None for row in scope['missing'])))
        for row in scope['missing']:
            with self.subTest(material=row['id']), self.assertRaises(ValueError):
                stock.validate_targets([{'id': row['id'], 'name': row['name'], 'route': row['id'], 'target': 20}])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = stock.StockStore(0, self.temp.name)

    def test_account_isolation_durable_readback_and_own_lock(self):
        rows = [dict(stock.material_options()[0], target=20)]
        self.store.update('targets', rows)
        self.store.update('pending', {'pending': True, 'cost': 20})
        self.assertEqual(self.store.read()['targets'], rows)
        self.assertEqual(stock.StockStore(1, self.temp.name).read()['targets'], [])
        lock = self.store.path.with_suffix('.json.lock')
        lock.write_bytes(b'other-owner')
        with self.assertRaises(FileExistsError):
            self.store.update('pending', {}, expected_pending=self.store.read()['pending'])
        self.assertEqual(lock.read_bytes(), b'other-owner')
        self.assertTrue(self.store.read()['pending'])
        before = self.store.path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.update('schema', 'wrong')
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_atomic_save_failure_preserves_pending_and_no_lock_leak(self):
        self.store.update('pending', {'pending': True})
        before = self.store.path.read_bytes()
        with patch.object(stock.os, 'replace', side_effect=OSError('disk-full')), self.assertRaises(OSError):
            self.store.update('pending', {}, expected_pending=self.store.read()['pending'])
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse(self.store.path.with_suffix('.json.lock').exists())
        self.assertEqual(list(self.store.path.parent.glob('*.tmp')), [])

    def test_wrong_account_or_invalid_shape_refused(self):
        self.store.update('targets', [])
        data = self.store.read()
        for key, value in (('instance_idx', 1), ('pending', []), ('history', [])):
            corrupt = dict(data, **{key: value})
            self.store.path.write_text(json.dumps(corrupt), encoding='utf-8')
            with self.assertRaises(ValueError):
                self.store.read()
        for index in (-1, True, 100):
            with self.assertRaises(ValueError):
                stock.StockStore(index, self.temp.name)

    def test_native_progress_only_in_temporary_plan_no_refills_or_loop(self):
        original = Mock()
        plan = NS(plan_id='owned', run_times=0)
        config = stock.EphemeralChargePlan(plan)
        ctx = NS(current_instance_idx=0, run_context=original, notify_config=NS(enable_notify=True))
        proxy = stock.ContextProxy(ctx, config)
        self.assertFalse(proxy.notify_config.enable_notify)
        self.assertTrue(ctx.notify_config.enable_notify)
        self.assertIs(proxy.run_context.get_config('charge_plan', 0, 'one_dragon'), config)
        with self.assertRaises(RuntimeError):
            proxy.run_context.get_config('charge_plan', 1, 'one_dragon')
        self.assertFalse(config.loop or config.double_reward or config.is_restore_charge_enabled)
        config.add_plan_run_times(plan)
        self.assertEqual(plan.run_times, 1)
        self.assertTrue(config.all_plan_finished())
        with self.assertRaises(RuntimeError):
            config.add_plan_run_times(plan)
        original.get_config.assert_not_called()

    def test_paid_hunt_does_not_access_production_weekly_config_or_run_record(self):
        original = Mock()
        config = stock.EphemeralChargePlan(NS(plan_id='own', run_times=0))
        proxy = stock.RunContextProxy(original, 0, config)
        self.assertIs(proxy.get_config('notorious_hunt', 0, 'one_dragon'), config)
        record = proxy.get_run_record('notorious_hunt', 0)
        self.assertEqual(record.left_times, 0)
        record.left_times = -1
        self.assertEqual(stock.RunContextProxy(original, 0, config).hunt_record.left_times, 0)
        for method, arguments in ((proxy.get_config, ('notorious_hunt', 1, 'one_dragon')), (proxy.get_run_record, ('notorious_hunt', 1))):
            with self.assertRaises(RuntimeError):
                method(*arguments)
        original.get_config.assert_not_called()
        original.get_run_record.assert_not_called()

    def paid_entry(self, changes=None, confidence=0.99):
        texts = {'标题-副本名称': '初生死路屠夫', '难度选择入口': 'Lv.65', '剩余奖励次数': '剩余奖励次数', '剩余次数': '3', '按钮-深度追猎-ON': 'ON', '文本-需要电量': '60', '文本-剩余电量': '120'}
        texts.update(changes or {})

        def read(frame, area):
            return {texts[area]: NS(max=NS(confidence=confidence))}
        return NS(plan=NS(mission_type_name='初生死路屠夫'), screenshot=Mock(return_value='fresh'), ctx=NS(screen_loader=NS(get_area=lambda screen, name: NS(rect=name)), ocr=NS(crop_and_run_ocr=read)))

    def test_paid_hunt_entry_requires_two_fresh_frames_and_journal_checks(self):
        op, guard, journal = (self.paid_entry(), Mock(), Mock())
        with patch.object(stock.time, 'sleep'):
            stock.verify_paid_hunt_entry(op, guard, journal)
        self.assertEqual(op.screenshot.call_count, 2)
        self.assertEqual(journal.call_count, 2)
        self.assertEqual(guard.call_count, 4)

    def test_paid_hunt_unknown_boss_mode_level_cost_or_battery_never_admits(self):
        invalid = [('标题-副本名称', '未知复合侵蚀体'), ('难度选择入口', 'Lv.60'), ('按钮-深度追猎-ON', 'OFF'), ('文本-需要电量', '160'), ('文本-需要电量', '60.5'), ('文本-剩余电量', '59'), ('文本-剩余电量', '-120'), ('文本-剩余电量', '2400')]
        for name, value in invalid:
            with self.subTest(name=name, value=value), self.assertRaises(RuntimeError):
                stock.verify_paid_hunt_entry(self.paid_entry({name: value}), Mock(), Mock())
        for confidence in (True, 0.89, float('nan'), float('inf')):
            with self.subTest(confidence=confidence), self.assertRaises(RuntimeError):
                stock.verify_paid_hunt_entry(self.paid_entry(confidence=confidence), Mock(), Mock())

    def test_paid_hunt_journal_failure_stops_before_screenshot(self):
        op = self.paid_entry()
        with self.assertRaisesRegex(RuntimeError, 'pending-changed'):
            stock.verify_paid_hunt_entry(op, Mock(), Mock(side_effect=RuntimeError('pending-changed')))
        op.screenshot.assert_not_called()

    def test_paid_hunt_terminal_free_quota_refusal_preserves_pending_until_policy_verification(self):
        route = stock.ROUTES['ferocious-grip']
        plan = NS(plan_id='owned', run_times=0, plan_times=1)
        op = NS(ctx=NS(current_instance_idx=0, run_context=Mock()))
        transport_module = ModuleType('zzz_od.operation.compendium.tp_by_compendium')
        transport = Mock(return_value=NS(execute=lambda: NS(success=True)))
        transport_module.TransportByCompendium = transport
        pending = {'pending': True, 'cost': 60, 'route': 'ferocious-grip', 'material_id': 'ferocious-grip'}
        battle = NS(STATUS_BLOCKED_BY_LEFT_TIMES='free-left', paid_entry_attempted=False, start_attempted=False, execute=lambda: NS(success=True, status='free-left'))
        reading = self.paid_entry()
        battle.plan, battle.screenshot, battle.ctx = (reading.plan, reading.screenshot, reading.ctx)
        self.store.update('pending', pending)
        with patch.dict('sys.modules', {transport_module.__name__: transport_module}), patch.object(stock, 'build_plan', return_value=plan), patch.object(stock, 'native_battle', return_value=battle):
            outcome = stock.farm_once(op, self.store, route, Mock())
            self.assertEqual(outcome, {'state': 'route_unavailable', 'reason': 'free_weekly_quota_remaining'})
            self.assertEqual(self.store.read()['pending'], pending)
            transport.assert_called_once()
            self.assertEqual(transport.call_args.args[1:], ('训练', '恶名狩猎', '初生死路屠夫'))
            for field in ('paid_entry_attempted', 'start_attempted'):
                setattr(battle, field, True)
                with self.assertRaises(RuntimeError):
                    stock.farm_once(op, self.store, route, Mock())
                self.assertEqual(self.store.read()['pending'], pending)
                setattr(battle, field, False)

    def test_free_hunt_refusal_requires_two_positive_exact_fresh_quota_readings(self):
        op, guard, journal = (self.paid_entry(), Mock(), Mock())
        with patch.object(stock.time, 'sleep'):
            stock.verify_free_hunt_refusal(op, guard, journal)
        self.assertEqual(op.screenshot.call_count, 2)
        self.assertEqual(journal.call_count, 2)
        for changes in ({'剩余次数': '0'}, {'剩余次数': '13'}, {'剩余次数': '-1'}, {'剩余次数': '1/3'}, {'剩余次数': '1.0'}, {'剩余奖励次数': '电量消耗'}, {'标题-副本名称': '另一首领'}):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                stock.verify_free_hunt_refusal(self.paid_entry(changes), Mock(), Mock())
        with self.assertRaises(RuntimeError):
            stock.verify_free_hunt_refusal(self.paid_entry(confidence=0.89), Mock(), Mock())

    def test_native_refusal_with_unknown_quota_keeps_pending(self):
        reading = self.paid_entry({'剩余次数': '0'})
        battle = NS(STATUS_BLOCKED_BY_LEFT_TIMES='free-left', paid_entry_attempted=False, start_attempted=False, execute=lambda: NS(success=True, status='free-left'), plan=reading.plan, screenshot=reading.screenshot, ctx=reading.ctx)
        module = ModuleType('zzz_od.operation.compendium.tp_by_compendium')
        module.TransportByCompendium = lambda *a: NS(execute=lambda: NS(success=True))
        pending = dict(pending=True, cost=60, route='ferocious-grip', material_id='ferocious-grip')
        self.store.update('pending', pending)
        with patch.dict('sys.modules', {module.__name__: module}), patch.object(stock, 'build_plan', return_value=NS(plan_id='own', run_times=0)), patch.object(stock, 'native_battle', return_value=battle), self.assertRaisesRegex(RuntimeError, '未核实'):
            stock.farm_once(NS(ctx=NS(current_instance_idx=0, run_context=Mock())), self.store, stock.ROUTES['ferocious-grip'], Mock())
        self.assertEqual(self.store.read()['pending'], pending)

    def test_natural_ocr_anchor_requires_unique_explicit_battery(self):

        def match(x):
            return NS(x=x, w=20)
        self.assertEqual(stock.natural_value({'120/240': [match(163)]}), 120)
        self.assertEqual(stock.natural_value({'0/240': [match(163)]}), 0)
        for value in ({}, {'2400/240': [match(163)]}, {'999': [match(163)]}, {'120/240': [match(485)]}, {'120/240': [match(163)], '80/240': [match(163)]}):
            with self.assertRaises(RuntimeError):
                stock.natural_value(value)

    def test_malformed_battery_cannot_authorize_farming(self):
        for text in ('-20/240', '−20/240', '+20/240', '12.5/240', '.20/240', '120/240.5', '120/2400', '1200/240'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                stock.natural_value({text: [NS(x=163, w=20)]})
        for current in (0, 20, 60, 239, 240):
            with self.subTest(current=current):
                self.assertEqual(stock.natural_value({f'电量 {current} / 240': [NS(x=163, w=20)]}), current)

    def test_guard_latches_loss_allows_only_pure_key_up(self):

        def move_w(press=False, press_time=None, release=False):
            return {'release': release}
        original = NS(click=Mock(), move_w=move_w, btn_release=Mock())
        guard = Mock()
        proxy = stock.GuardedController(original, guard)
        proxy.click()
        original.click.assert_called_once()
        guard.side_effect = RuntimeError('focus-lost')
        with self.assertRaises(RuntimeError):
            proxy.click()
        guard.side_effect = None
        with self.assertRaises(RuntimeError):
            proxy.click()
        proxy.btn_release('w')
        self.assertEqual(proxy.move_w(release=True), {'release': True})
        with self.assertRaises(RuntimeError):
            proxy.move_w(press=True, release=True)
        self.assertEqual(original.click.call_count, 1)

    def test_owned_controller_restored_and_foreign_battle_not_stopped(self):
        original = object()
        run = NS(current_application=object(), current_app_id='inventory_maintain')
        battle = NS(stop_auto_battle=Mock())
        ctx = NS(controller=original, run_context=run, auto_battle_context=battle)
        op = NS(ctx=ctx)
        with stock.controller_scope(op, lambda: None):
            self.assertIsInstance(ctx.controller, stock.GuardedController)
        self.assertIs(ctx.controller, original)
        battle.stop_auto_battle.assert_called_once()
        battle.stop_auto_battle.reset_mock()
        with stock.controller_scope(op, lambda: None):
            replacement = object()
            ctx.controller = replacement
            run.current_application = object()
        self.assertIs(ctx.controller, replacement)
        battle.stop_auto_battle.assert_not_called()

    def test_result_protocols_and_navigation_multiple_rounds(self):
        stock.require_success(NS(success=True), 'native')
        stock.require_success(NS(is_success=True), 'round')
        with self.assertRaises(RuntimeError):
            stock.require_success(NS(is_success=False, status='fail'), 'round')
        module = ModuleType('zzz_od.operation.back_to_normal_world')
        module.BackToNormalWorld = lambda *a, **k: NS(execute=lambda: NS(success=True))
        op = NS(ctx=NS(cv_service=NS(run_pipeline=lambda *a: NS(ocr_result={'55/240': [NS(x=163, w=20)]}))), screenshot=Mock(return_value='fresh-frame'), round_by_goto_screen=Mock(side_effect=[NS(is_success=False, is_fail=False), NS(is_success=True, is_fail=False)]))
        with patch.dict('sys.modules', {module.__name__: module}), patch.object(stock.time, 'sleep'):
            self.assertEqual(stock.read_natural(op, Mock()), 55)
        self.assertEqual(op.screenshot.call_count, 4)
        self.assertEqual(op.round_by_goto_screen.call_count, 2)

    def test_supported_menu_only_exact_calibrated_materials(self):
        options = stock.material_options()
        self.assertEqual(len(options), 97)
        self.assertIn('ferocious-grip', {row['id'] for row in options})
        rows = [dict(options[0], target=20)]
        self.assertEqual(stock.validate_targets(rows), rows)
        rows[0]['name'] = 'wrong-quality'
        with self.assertRaises(ValueError):
            stock.validate_targets(rows)

    def test_resource_version_mismatch_blocks_before_any_navigation(self):
        module = ModuleType('zzz_od.application.inventory_inspection.inventory_inspection')
        current = {'game_exe_sha256': 'current', 'resource_fingerprints': {'res': 'current'}}
        module.lane_matches = Mock(return_value=True)
        module.native_window_identity = Mock(return_value={'pid': 1, 'path': str(Path(self.temp.name) / 'ZenlessZoneZero.exe'), 'created': 'pinned'})
        bridge = NS(probe=NS(SPECS={'zzz': ['ZenlessZoneZero.exe']}), same_identity=Mock(return_value=True))
        module.load_module = Mock(return_value=bridge)
        module.NativeVersions = lambda *args: lambda: current
        op = NS(inventory_root=ROOT, ctx=NS(run_context=NS(current_application=object()), controller=Mock()))
        with patch.dict('sys.modules', {module.__name__: module, 'psutil': ModuleType('psutil'), 'win32gui': ModuleType('win32gui'), 'win32process': ModuleType('win32process')}):
            with self.assertRaisesRegex(RuntimeError, '版本不一致'):
                stock.make_guard(op, {'game_exe_sha256': 'old', 'resource_fingerprints': {'res': 'old'}})
            op.ctx.controller.assert_not_called()
            guard = stock.make_guard(op, current)
            guard()
            current['resource_fingerprints'] = {'res': 'changed'}
            with self.assertRaisesRegex(RuntimeError, '版本改变'):
                guard()

    def test_farming_calls_native_once_only_after_matching_durable_pending(self):
        route_id = next(iter(stock.ROUTES))
        route = stock.ROUTES[route_id]
        plan = NS(plan_id='owned', run_times=0, plan_times=1)
        state = NS(last_check_end_result='普通战斗-完成')
        op = NS(ctx=NS(current_instance_idx=0, run_context=Mock(), auto_battle_context=state))
        transport_module = ModuleType('zzz_od.operation.compendium.tp_by_compendium')
        combat_module = ModuleType('zzz_od.operation.compendium.combat_simulation')
        transport = Mock(return_value=NS(execute=lambda: NS(success=True)))
        transport_module.TransportByCompendium = transport
        contexts = []

        def battle(ctx, selected):
            contexts.append(ctx)

            def execute():
                self.assertIs(ctx.run_context.get_config('charge_plan', 0, 'default'), ctx.run_context.config)
                self.assertFalse(ctx.run_context.config.is_restore_charge_enabled)
                ctx.run_context.config.add_plan_run_times(selected)
                return NS(success=True)
            return NS(execute=execute)
        combat_module.CombatSimulation = battle
        pending = {'pending': True, 'cost': 20, 'route': route_id, 'material_id': route['materials'][0]}
        with patch.dict('sys.modules', {transport_module.__name__: transport_module, combat_module.__name__: combat_module}), patch.object(stock, 'build_plan', return_value=plan):
            for invalid in ({}, dict(pending, cost=60), dict(pending, route='wrong'), dict(pending, material_id='wrong-quality')):
                self.store.update('pending', {}, expected_pending=self.store.read()['pending'])
                self.store.update('pending', invalid)
                with self.assertRaises(RuntimeError):
                    stock.farm_once(op, self.store, route, lambda: None)
            transport.assert_not_called()
            self.store.update('pending', {}, expected_pending=self.store.read()['pending'])
            self.store.update('pending', pending)
            stock.farm_once(op, self.store, route, lambda: None)
            self.assertEqual(plan.run_times, 1)
            self.assertEqual(len(contexts), 1)
            self.assertEqual(self.store.read()['pending'], pending)
            plan.run_times = 0
            state.last_check_end_result = '普通战斗-撤退'
            with self.assertRaisesRegex(RuntimeError, '战斗胜利'):
                stock.farm_once(op, self.store, route, lambda: None)
            self.assertEqual(self.store.read()['pending'], pending)

    def test_fresh_inspect_one_native_battle_and_stamina_shortage(self):
        module = ModuleType('zzz_od.application.inventory_inspection.inventory_inspection')
        module.prepare = Mock(return_value=(None, None, {}))
        module.load_module = lambda *a: None
        module.run_inventory_inspection = Mock()
        back = ModuleType('zzz_od.operation.back_to_normal_world')
        back.BackToNormalWorld = lambda *a, **k: NS(execute=lambda: NS(success=True))
        logs = ModuleType('one_dragon.utils.log_utils')
        logs.log = Mock()
        rows = [dict(stock.material_options()[0], target=2)]
        self.store.update('targets', rows)

        def report(*a, **k):
            now = datetime.now(timezone.utc).isoformat()
            return {'schema': 'inventory-report/v1', 'game': 'zzz', 'materials': [dict(rows[0], quantity=0 if module.run_inventory_inspection.call_count == 1 else 2, status='confirmed', evidence=[{'captured_at': now}] * 2)]}
        module.run_inventory_inspection.side_effect = report
        run = NS(current_application=object(), current_app_id='inventory_maintain')
        original_controller = object()
        op = NS(inventory_root=Path(self.temp.name), ctx=NS(current_instance_idx=0, run_context=run, controller=original_controller, auto_battle_context=NS(stop_auto_battle=Mock())))

        def farm(*a):
            self.assertTrue(self.store.read()['pending']['pending'])
            self.assertEqual(self.store.read()['pending']['cost'], 20)
        with patch.dict('sys.modules', {module.__name__: module, back.__name__: back, logs.__name__: logs}), patch.object(stock, 'validate_targets', return_value=rows), patch.object(stock, 'build_plan'), patch.object(stock, 'make_guard', return_value=lambda: None), patch.object(stock, 'policy', return_value=stock.policy(ROOT)), patch.object(stock, 'read_natural', side_effect=[40, 20]), patch.object(stock, 'farm_once', side_effect=farm) as farming:
            result = stock.run_maintain(op)
        self.assertEqual(result['state'], 'targets_met')
        self.assertEqual(len(result['receipts']), 1)
        farming.assert_called_once()
        self.assertFalse(self.store.read()['pending'])
        self.assertIs(op.ctx.controller, original_controller)
        self.assertEqual(self.store.read()['history']['materials'][0]['quantity'], 2)
if __name__ == '__main__':
    unittest.main()
