import contextlib
from io import StringIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import build, check_public_files as privacy
from xiaoai_pc.config import data_directory


class PublicFilesTests(unittest.TestCase):
    def test_docs_reject_absolute_paths_but_accept_urls_and_environment_placeholders(self):
        private = ('Z:' + '/Projects/fixture/app').encode()
        self.assertTrue(privacy.inspect_file('AGENTS.md', private))
        self.assertEqual(privacy.inspect_file('README.md', b'https://example.com %LOCALAPPDATA%/Assistant'), [])
        self.assertEqual(privacy.inspect_file('tests/fixture.py', private), [])

    def test_user_home_paths_rejected_even_in_test_fixtures(self):
        for value in ('/'.join(('Z:', 'Users', 'fixture', 'app')), '/'.join(('', 'home', 'fixture', 'app'))):
            self.assertTrue(privacy.inspect_file('tests/fixture.py', value.encode()))

    def test_private_runtime_file_names_rejected(self):
        for name in ('config.json', 'config.before-install.json', '.env.local', 'session.dpapi',
                     'config.json.bak', 'assistant.log.1', 'desktop.lnk', '.idea/settings.xml'):
            self.assertTrue(privacy.inspect_file(name, b'fixture'), name)
        self.assertEqual(privacy.inspect_file('config.example.json', b'{"xiaomi":{"device_id":""}}'), [])

    def test_example_must_not_contain_device_id_or_application_path(self):
        for example in ({'xiaomi': {'device_id': 'fixture'}}, {'commands': [{'path': 'fixture.exe'}]}):
            self.assertTrue(privacy.inspect_file('config.example.json', json.dumps(example).encode()))

    def test_credential_findings_do_not_echo_the_value(self):
        secret = 'ghp_' + 'A' * 40
        findings = privacy.inspect_file('notes.md', secret.encode())
        self.assertIn('possible credential', findings)
        self.assertNotIn(secret, str(findings))

    def test_build_rejects_private_document_even_if_manifest_lists_it(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'scripts').mkdir()
            (root / 'scripts/source-files.txt').write_text('README.md\n', encoding='utf-8')
            (root / 'README.md').write_text('Z:' + '/Projects/fixture', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'privacy check failed'):
                build.write_application_source(root / 'source.zip', root)

    def test_staged_check_reads_index_not_clean_working_copy(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            doc = root / 'README.md'
            doc.write_text('Z:' + '/Projects/fixture', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=root, check=True)
            doc.write_text('No private data.', encoding='utf-8')
            output = StringIO()
            with patch.object(privacy, 'ROOT', root), patch('sys.argv', ['check', '--staged']), contextlib.redirect_stdout(output):
                self.assertEqual(privacy.main(), 1)
            self.assertIn('absolute machine path', output.getvalue())
            self.assertNotIn('Projects/fixture', output.getvalue())

    def test_runtime_data_directory_is_derived_from_current_machine(self):
        with TemporaryDirectory() as folder, patch.dict('os.environ', {'LOCALAPPDATA': folder}):
            self.assertEqual(data_directory(), Path(folder) / 'TangerineXiaoAiAssistant')


if __name__ == '__main__':
    unittest.main()
