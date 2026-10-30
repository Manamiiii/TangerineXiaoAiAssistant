import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from xiaoai_pc.config import DEFAULT_CONFIG, load, save
from xiaoai_pc.runtime import single_instance
from xiaoai_pc.secure import SecretStore, SecretStoreError
from xiaoai_pc.workbuddy import DisabledWorkBuddy, MockWorkBuddy


@unittest.skipUnless(os.name == "nt", "Requires Windows")
class WindowsTests(unittest.TestCase):
    def test_real_dpapi_roundtrip_and_tamper_detection(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "session.dpapi"
            store = SecretStore(path)
            token = {"passToken": "TEST-SECRET-ONLY", "micoapi": ["ssecurity", "TEST-SERVICE"]}
            store.save(token)
            self.assertNotIn(b"TEST-SECRET-ONLY", path.read_bytes())
            self.assertEqual(store.load(), token)
            store.save({"renewed": True})
            self.assertEqual(store.load(), {"renewed": True})
            path.write_bytes(b"invalid encrypted data")
            with self.assertRaises(SecretStoreError):
                store.load()
            store.clear()
            self.assertEqual(store.load(), {})

    def test_single_instance_blocks_second_process(self):
        with TemporaryDirectory() as folder:
            with single_instance(Path(folder)):
                completed = subprocess.run([sys.executable, "-m", "xiaoai_pc", "--data-dir", folder, "init"],
                                           capture_output=True, encoding="utf-8")
                self.assertEqual(completed.returncode, 2)
                self.assertIn("已有实例", completed.stderr)
            with single_instance(Path(folder)):
                pass

    def test_cli_init_and_dry_run_without_credentials(self):
        with TemporaryDirectory() as folder:
            command = [sys.executable, "-m", "xiaoai_pc", "--data-dir", folder]
            result = subprocess.run(command + ["init"], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            path = Path(folder) / "config.json"
            cfg = load(path)
            cfg["tts_reply"] = False
            save(path, cfg)
            result = subprocess.run(command + ["init"], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0)
            self.assertFalse(load(path)["tts_reply"])
            result = subprocess.run(command + ["test-command", "小爱同学，让电脑打开B站"], capture_output=True, encoding="utf-8")
            self.assertEqual(json.loads(result.stdout)["code"], "dry_run")
            self.assertFalse((Path(folder) / "xiaomi.dpapi").exists())
            result = subprocess.run(command + ["run"], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2)
            self.assertIn("login", result.stderr)


class AdapterTests(unittest.TestCase):
    def test_workbuddy_never_claims_real_submission(self):
        self.assertEqual(DisabledWorkBuddy().submit("test").status, "not_configured")
        mock = MockWorkBuddy()
        result = mock.submit("整理下载文件夹")
        self.assertEqual(result.status, "simulated")
        self.assertIn("未发送", result.feedback)
        self.assertEqual(mock.status(result.message_id), result)
