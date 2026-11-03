from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import uuid
from unittest.mock import patch

from xiaoai_pc.identity import PRODUCTION, fixture_identity, validate
from xiaoai_pc.lifecycle import lifecycle_guard
from xiaoai_pc.runtime import single_instance
from scripts.build_installer import quote, verified_payload


class InstallerTests(unittest.TestCase):
    def test_fixture_separates_every_persistent_identity(self):
        a, b = fixture_identity(str(uuid.uuid4())), fixture_identity(str(uuid.uuid4()))
        for key in ('app_id', 'guid', 'directory_name', 'data_folder', 'startup_value', 'display_name'):
            self.assertNotEqual(a[key], PRODUCTION[key])
            self.assertNotEqual(a[key], b[key])
        self.assertEqual(validate(a), a)
        with self.assertRaises(ValueError):
            fixture_identity(PRODUCTION['guid'])
        changed = deepcopy(a)
        changed['data_folder'] = PRODUCTION['data_folder']
        with self.assertRaises(RuntimeError):
            validate(changed)

    def test_production_data_identity_remains_compatible(self):
        self.assertEqual(PRODUCTION['data_folder'], 'TangerineXiaoAiAssistant')
        self.assertEqual(PRODUCTION['startup_value'], 'TangerineXiaoAiAssistant')
        self.assertFalse(PRODUCTION['fixture'])

    def test_production_rejects_fixture_session_before_opening_window_or_config(self):
        from xiaoai_pc import desktop
        with TemporaryDirectory() as folder, patch.object(desktop.tk, 'Tk') as window:
            with self.assertRaises(RuntimeError):
                desktop.run(Path(folder), Path(folder) / 'config.json', fixture=True)
            window.assert_not_called()
            self.assertFalse((Path(folder) / 'config.json').exists())

    def test_nsis_quotes_dollar_and_quotes_and_rejects_newlines(self):
        self.assertEqual(quote('$"'), '"$$$\\""')
        with self.assertRaises(ValueError):
            quote('example\nFile bad')

    def child_lock(self, folder, exclusive):
        code = ('from pathlib import Path; from xiaoai_pc.lifecycle import lifecycle_guard; '
                'import sys;\ntry:\n with lifecycle_guard(Path(sys.argv[1]), exclusive=' + str(exclusive) + '): pass\n'
                'except RuntimeError: sys.exit(10)\n')
        return subprocess.run([sys.executable, '-c', code, folder], capture_output=True).returncode

    def test_runtime_locks_share_but_block_installer_and_release(self):
        with TemporaryDirectory() as folder:
            with lifecycle_guard(Path(folder)):
                self.assertEqual(self.child_lock(folder, False), 0)
                self.assertEqual(self.child_lock(folder, True), 10)
            self.assertEqual(self.child_lock(folder, True), 0)

    def test_installer_exclusive_lock_blocks_runtime(self):
        with TemporaryDirectory() as folder:
            with lifecycle_guard(Path(folder), exclusive=True):
                self.assertEqual(self.child_lock(folder, False), 10)
                self.assertEqual(self.child_lock(folder, True), 10)

    def test_payload_requires_exact_files_and_hashes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            payload = root / 'app.exe'
            payload.write_bytes(b'fixture')
            info = {'identity': PRODUCTION, 'platform': 'windows-x64',
                    'files': {'app.exe': hashlib.sha256(payload.read_bytes()).hexdigest()}}
            (root / 'build-info.json').write_text(json.dumps(info), encoding='utf-8')
            self.assertEqual(verified_payload(root)[1], PRODUCTION)
            payload.write_bytes(b'changed')
            with self.assertRaises(RuntimeError):
                verified_payload(root)
            payload.write_bytes(b'fixture')
            (root / 'unexpected.txt').write_text('do not package')
            with self.assertRaises(RuntimeError):
                verified_payload(root)


if __name__ == '__main__':
    unittest.main()
