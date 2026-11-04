import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zzz_od.graphics_profiles import profiles as gfx


class GraphicsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'GENERAL_DATA.bin'
        self.values = json.loads(gfx.PROFILES.read_text(encoding='utf-8'))['profiles'][
            'low'
        ]['values']
        self.doc = {
            'SystemSettingDataMap': {
                k: {'$Type': gfx.ITEM_TYPE, 'Version': 0, 'Data': 3}
                for k in gfx.ALLOWED
            },
            'unrelated': {'text': '中文音频与键位 🎮', 'version': 'native'},
        }
        self.doc['SystemSettingDataMap']['42'] = {
            '$Type': gfx.ITEM_TYPE,
            'Version': 9,
            'Data': 4,
        }
        self.doc['SystemSettingDataMap']['31009'] = {
            '$Type': gfx.ITEM_TYPE,
            'Version': 0,
            'Data': 0,
        }
        self.raw = gfx.encode_document(self.doc)
        self.path.write_bytes(self.raw)

    def apply(self, idle=lambda: None):
        return gfx.apply(self.values, self.path, self.folder / 'backups', idle)

    def test_unicode_roundtrip(self):
        self.assertEqual(gfx.reader.decode_document(self.raw), self.doc)

    def test_competing_writer_refused_until_lock_released(self):
        lock = self.path.with_name(self.path.name + '.graphics.lock')
        with gfx.native_lock(lock), self.assertRaises(OSError):
            self.apply()
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertTrue(self.apply()['changed'])

    def test_only_calibrated_fields_changed(self):
        result = self.apply()
        current = gfx.reader.read_document(self.path)
        self.assertEqual(current['unrelated'], self.doc['unrelated'])
        for key in ('42', '31009'):
            self.assertEqual(
                current['SystemSettingDataMap'][key],
                self.doc['SystemSettingDataMap'][key],
            )
        self.assertEqual(Path(result['backup']).read_bytes(), self.raw)
        self.assertEqual(current, gfx.merge_graphics(self.doc, self.values))

    def test_noop_does_not_rewrite_or_backup(self):
        self.path.write_bytes(
            gfx.encode_document(gfx.merge_graphics(self.doc, self.values))
        )
        before = self.path.read_bytes()
        self.assertFalse(self.apply()['changed'])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.folder / 'backups').exists())

    def test_unknown_field_rejected(self):
        bad = dict(self.values, **{'42': 0})
        with self.assertRaises(ValueError):
            gfx.merge_graphics(self.doc, bad)

    def test_missing_field_rejected(self):
        del self.doc['SystemSettingDataMap']['99']
        with self.assertRaises(ValueError):
            gfx.merge_graphics(self.doc, self.values)

    def test_bool_or_type_change_rejected(self):
        for data in (False, '3'):
            self.doc['SystemSettingDataMap']['99']['Data'] = data
            with self.assertRaises(ValueError):
                gfx.merge_graphics(self.doc, self.values)
        self.doc['SystemSettingDataMap']['99'] = {'$Type': 'unknown', 'Data': 0}
        with self.assertRaises(ValueError):
            gfx.merge_graphics(self.doc, self.values)

    def test_running_guard_no_mutation(self):

        def running():
            raise RuntimeError('running')

        with self.assertRaises(RuntimeError):
            self.apply(running)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_idle_checked_again_before_commit(self):
        calls = []

        def running_later():
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('now running')

        with self.assertRaises(RuntimeError):
            self.apply(running_later)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_concurrent_native_save_preserved(self):
        calls = []
        newer = gfx.encode_document(dict(self.doc, native_change='kept'))

        def concurrent():
            calls.append(1)
            if len(calls) == 2:
                self.path.write_bytes(newer)

        with self.assertRaisesRegex(RuntimeError, 'concurrently'):
            self.apply(concurrent)
        self.assertEqual(self.path.read_bytes(), newer)

    def test_backup_failure_no_native_write(self):
        (self.folder / 'backups').write_text('not a folder')
        with self.assertRaises(OSError):
            self.apply()
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_readback_failure_rolls_back(self):
        with (
            patch.object(
                gfx.reader, 'read_document', side_effect=ValueError('bad readback')
            ),
            self.assertRaises(ValueError),
        ):
            self.apply()
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_native_format_corruption_rejected(self):
        self.path.write_bytes(b'invalid format')
        with self.assertRaises((ValueError, EOFError)):
            self.apply()
        self.assertEqual(self.path.read_bytes(), b'invalid format')

    def test_native_utf8_is_required_not_just_python_decode(self):
        for padding in range(30):
            doc = dict(self.doc, account='x' * padding + '@example')
            raw = gfx.encode_document(doc)
            try:
                gfx.validate_native_utf8(raw)
            except UnicodeDecodeError:
                self.assertEqual(gfx.reader.decode_document(raw), doc)
                break
        else:
            self.fail('Regression fixture did not exercise native UTF-8 rejection')

    def test_preserves_whitespace_and_full_non_graphics_structure(self):
        text = '\r\n' + json.dumps(self.doc, indent=4, ensure_ascii=True).replace(
            '\n', '\r\n'
        )
        stream = __import__('io').BytesIO()
        gfx.reader.load_codec().write_string(stream, text, gfx.reader.MAGIC)
        raw = stream.getvalue()
        new_raw = gfx.encode_graphics_patch(raw, self.doc, self.values)
        actual = gfx.reader.load_codec().read_string(
            __import__('io').BytesIO(new_raw), gfx.reader.MAGIC
        )
        self.assertEqual(actual.count('\r\n'), text.count('\r\n'))
        self.assertEqual(len(new_raw), len(raw))
        gfx.validate_native_utf8(new_raw)


if __name__ == '__main__':
    unittest.main()
