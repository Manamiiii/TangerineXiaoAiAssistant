import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xiaoai_pc import cli, config, storage
from xiaoai_pc.runtime import single_instance
from xiaoai_pc.lifecycle import lifecycle_guard
from xiaoai_pc.secure import SecretStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        env = patch.dict(os.environ, LOCALAPPDATA=str(self.root))
        env.start()
        self.addCleanup(env.stop)
        self.old = storage.legacy_directory()
        self.new = storage.default_directory()

    def seed(self):
        config.save(self.old / "config.json", config.DEFAULT_CONFIG)
        updated = config.load(self.old / "config.json")
        updated["tts_reply"] = False
        config.save(self.old / "config.json", updated)
        SecretStore(self.old / "xiaomi.dpapi").save({"fixture": "synthetic-session"})
        (self.old / "assistant.log").write_bytes(b"synthetic status\n")
        return {p.name: p.read_bytes() for p in self.old.iterdir()}

    def test_migrates_exact_bytes_reopens_and_blocks_old_config(self):
        original = self.seed()
        self.assertEqual(cli.main(["init"]), 0)
        for name, data in original.items():
            self.assertEqual(storage.data_file(self.new, name).read_bytes(), data)
            self.assertEqual((self.old / storage.ORIGINALS / name).read_bytes(), data)
        self.assertEqual(SecretStore(storage.data_file(self.new, "xiaomi.dpapi")).load(),
                         {"fixture": "synthetic-session"})
        with self.assertRaises(config.ConfigError):
            config.load(self.old / "config.json")
        self.assertEqual(cli.main(["test-command", "让电脑打开B站"]), 0)
        self.assertEqual(cli.main(["--data-dir", str(self.old), "init"]), 2)
        self.assertEqual(cli.main(["--data-dir", str(self.new), "init"]), 0)

    def test_fresh_default_and_backup_use_categories(self):
        self.assertEqual(cli.main(["init"]), 0)
        path = self.new / "Config/config.json"
        before = path.read_bytes()
        cfg = config.load(path)
        cfg["tts_reply"] = False
        config.save(path, cfg)
        self.assertEqual((self.new / "Backups/config.json.bak").read_bytes(), before)
        self.assertFalse((self.new / "config.json").exists())
        self.assertEqual(cli.main(["init"]), 0)

    def test_custom_directory_and_external_config_stay_in_place(self):
        custom = self.root / "custom"
        external = self.root / "outside/settings.json"
        self.assertEqual(cli.main(["--data-dir", str(custom), "--config", str(external), "init"]), 0)
        self.assertTrue(external.is_file())
        self.assertFalse(self.new.exists())
        self.assertFalse(self.old.exists())
        self.assertEqual(storage.data_file(custom, "xiaomi.dpapi"), custom / "xiaomi.dpapi")

    def test_equivalent_default_path_uses_same_layout_and_missing_config_stops(self):
        alias = self.new / ".." / self.new.name
        self.assertEqual(cli.main(["--data-dir", str(alias), "init"]), 0)
        self.assertTrue((self.new / "Config/config.json").exists())
        self.assertFalse((self.new / "config.json").exists())
        (self.new / "Config/config.json").unlink()
        self.assertEqual(cli.main(["init"]), 2)
        self.assertFalse((self.new / "Config/config.json").exists())

    def test_failed_atomic_blocker_keeps_original_config_readable(self):
        original = self.seed()
        with patch.object(config, "_atomic_write", side_effect=OSError("fixture replacement denied")):
            self.assertEqual(cli.main(["init"]), 2)
        self.assertEqual((self.old / "config.json").read_bytes(), original["config.json"])
        self.assertEqual((self.old / storage.ORIGINALS / "config.json").read_bytes(), original["config.json"])
        self.assertEqual(cli.main(["init"]), 2)

    def test_two_data_locations_conflict_without_changing_originals(self):
        original = self.seed()
        config.save(self.new / "Config/config.json", config.DEFAULT_CONFIG)
        before = (self.new / "Config/config.json").read_bytes()
        self.assertEqual(cli.main(["init"]), 2)
        self.assertFalse((self.old / storage.JOURNAL).exists())
        self.assertEqual((self.new / "Config/config.json").read_bytes(), before)
        for name, data in original.items():
            self.assertEqual((self.old / name).read_bytes(), data)

    def test_unknown_or_corrupt_legacy_data_is_not_reset(self):
        self.old.mkdir()
        path = self.old / "config.json"
        path.write_bytes(b"broken")
        self.assertEqual(cli.main(["init"]), 2)
        self.assertEqual(path.read_bytes(), b"broken")
        self.assertFalse((self.old / storage.JOURNAL).exists())
        path.unlink()
        config.save(path, config.DEFAULT_CONFIG)
        (self.old / "unknown.json").write_bytes(b"keep")
        self.assertEqual(cli.main(["init"]), 2)
        self.assertEqual((self.old / "unknown.json").read_bytes(), b"keep")

    def test_interrupted_migration_keeps_every_original_and_does_not_resume(self):
        for fail_at in range(1, 9):
            with self.subTest(write=fail_at), TemporaryDirectory(dir=self.root) as folder, \
                 patch.dict(os.environ, LOCALAPPDATA=folder):
                self.old = storage.legacy_directory()
                self.new = storage.default_directory()
                original = self.seed()
                real_write = storage._exclusive_write
                count = 0
                def interrupted(path, data):
                    nonlocal count
                    count += 1
                    if count == fail_at:
                        raise OSError("simulated disk failure")
                    real_write(path, data)
                with patch.object(storage, "_exclusive_write", side_effect=interrupted):
                    result = cli.main(["init"])
                if result == 0:
                    continue
                for name, data in original.items():
                    locations = [self.old / name, self.old / storage.ORIGINALS / name]
                    self.assertTrue(any(p.is_file() and p.read_bytes() == data for p in locations))
                if (self.old / storage.JOURNAL).exists() and not (self.new / "Runtime/layout.json").exists():
                    self.assertEqual(cli.main(["init"]), 2)

    def test_missing_or_tampered_marker_and_revived_old_data_stop_new_app(self):
        self.assertEqual(cli.main(["init"]), 0)
        (self.old / "xiaomi.dpapi").write_bytes(b"revived older program")
        self.assertEqual(cli.main(["init"]), 2)
        (self.old / "xiaomi.dpapi").unlink()
        (self.new / "Runtime/layout.json").unlink()
        self.assertEqual(cli.main(["init"]), 2)

    def test_old_running_instance_and_old_installer_block_migration(self):
        self.seed()
        for guard in (single_instance(self.old), lifecycle_guard(self.old, exclusive=True)):
            with guard:
                result = subprocess.run([sys.executable, "-m", "xiaoai_pc", "init"], capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.old / storage.JOURNAL).exists())

    def test_new_session_blocks_old_lock_and_duplicate_start(self):
        with storage.session(self.new):
            result = subprocess.run([sys.executable, "-m", "xiaoai_pc", "init"], capture_output=True)
            self.assertEqual(result.returncode, 2)
            with self.assertRaises(RuntimeError), single_instance(self.old):
                pass
            with self.assertRaises(RuntimeError), lifecycle_guard(self.old, exclusive=True):
                pass

    def test_junction_rejected_before_data_write(self):
        destination = self.root / "external"
        destination.mkdir()
        keep = destination / "keep.txt"
        keep.write_bytes(b"keep")
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.old), str(destination)],
                       check=True, capture_output=True)
        try:
            self.assertEqual(cli.main(["init"]), 2)
            self.assertEqual(list(destination.iterdir()), [keep])
        finally:
            self.assertTrue(self.old.is_junction())
            self.old.rmdir()


if __name__ == "__main__":
    unittest.main()
