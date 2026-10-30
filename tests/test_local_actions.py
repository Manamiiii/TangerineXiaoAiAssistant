from copy import deepcopy
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from xiaoai_pc import windows_actions as windows
from xiaoai_pc.commands import CommandRouter
from xiaoai_pc.config import ConfigError, DEFAULT_CONFIG, add_local_commands, load, save, validate
from xiaoai_pc.rules import parse_level


class LocalRuleTests(unittest.TestCase):
    def setUp(self):
        self.config = deepcopy(DEFAULT_CONFIG)
        self.router = CommandRouter(self.config)

    def test_arabic_and_chinese_percentages(self):
        for phrase, expected in (("把音量调到30", 30), ("音量调到三十", 30), ("音量调到百分之三十", 30),
                                 ("把音量设置为30%", 30), ("音量调到十", 10), ("音量调到一百", 100),
                                 ("音量调到零", 0), ("音量调到两", 2), ("音量调到九十九", 99),
                                 ("音量调到１００％", 100)):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.router.match("让电脑" + phrase)["level"], expected)
        for value in range(101):
            self.assertEqual(parse_level(str(value)), value)

    def test_invalid_volume_never_matches(self):
        for level in ("-1", "101", "99999", "30.5", "三零", "十零", "一百零一", "百分之30%", "30然后锁屏", "30 & calc"):
            with self.subTest(level=level):
                self.assertIsNone(self.router.match("让电脑把音量调到" + level))

    def test_dry_run_for_new_actions_has_no_side_effects(self):
        with patch.object(windows, "set_volume") as volume, patch.object(windows, "lock_workstation") as lock:
            for text in ("让电脑锁屏", "让电脑锁定电脑", "让电脑把音量调到30"):
                self.assertEqual(self.router.execute(text, dry_run=True).code, "dry_run")
        volume.assert_not_called()
        lock.assert_not_called()

    def test_volume_feedback_uses_actual_value_and_mute_state(self):
        with patch.object(windows, "set_volume", return_value=(30, True)) as volume:
            result = self.router.execute("让电脑把音量调到三十")
        volume.assert_called_once_with(30)
        self.assertTrue(result.ok)
        self.assertIn("百分之30", result.reply)
        self.assertIn("仍为静音", result.reply)

    def test_lock_feedback_is_only_a_request(self):
        with patch.object(windows, "lock_workstation") as lock:
            result = self.router.execute("让电脑锁定电脑")
        lock.assert_called_once_with()
        self.assertEqual(result.code, "lock_requested")
        self.assertIn("已请求", result.reply)
        for text in ("让电脑不要锁屏", "不要让电脑锁屏", "让电脑锁屏然后关机"):
            self.assertIsNone(self.router.match(text))

    def test_ambiguous_fixed_and_volume_rules_do_not_execute(self):
        self.config["commands"].append({"id": "bad", "action": "lock", "phrases": ["把音量调到30"]})
        router = CommandRouter(validate(self.config))
        self.assertIsNone(router.match("让电脑把音量调到30"))

    def test_configuration_rejects_parameter_and_template_abuse(self):
        bad_commands = [
            {"id": "bad", "action": "launch_app", "phrases": ["打开应用"], "path": r"C:\App\app.exe", "args": ["/c"]},
            {"id": "bad", "action": "launch_app", "phrases": ["打开{path}"], "path": r"C:\App\app.exe"},
            {"id": "bad", "action": "set_volume", "phrases": ["调音量"]},
            {"id": "bad", "action": "set_volume", "phrases": ["调音量{level}{level}"]},
            {"id": "bad", "action": "lock", "phrases": ["锁住"], "path": r"C:\App\app.exe"},
            {"id": "bad", "action": "lock", "phrases": ["锁住"], "reply": "错误成功描述"},
        ]
        for command in bad_commands:
            cfg = deepcopy(self.config)
            cfg["commands"].append(command)
            with self.subTest(command=command), self.assertRaises(ConfigError):
                validate(cfg)

    def test_app_rule_uses_only_registered_path(self):
        self.config["commands"].append({"id": "wechat", "action": "launch_app", "phrases": ["打开微信", "打开WeChat"], "path": r"C:\Apps\WeChat.exe"})
        router = CommandRouter(validate(self.config))
        with patch.object(windows, "launch_app") as launch:
            self.assertTrue(router.execute("让电脑打开微信").ok)
            self.assertFalse(router.execute("让电脑打开微信 --command evil").ok)
            self.assertFalse(router.execute(r"让电脑打开C:\Apps\WeChat.exe").ok)
        launch.assert_called_once_with(r"C:\Apps\WeChat.exe")

    def test_upgrade_is_idempotent_and_preserves_old_config(self):
        old = deepcopy(self.config)
        old["commands"] = old["commands"][:1]
        old["xiaomi"]["device_id"] = "test-speaker"
        old["trigger_prefixes"] = ["帮电脑"]
        upgraded, count = add_local_commands(old)
        self.assertEqual(count, 2)
        self.assertEqual(len(old["commands"]), 1)
        self.assertEqual(upgraded["xiaomi"], old["xiaomi"])
        self.assertEqual(upgraded["trigger_prefixes"], old["trigger_prefixes"])
        self.assertEqual(add_local_commands(upgraded), (upgraded, 0))


class NativeActionTests(unittest.TestCase):
    def test_reject_interpreters_scripts_and_nonlocal_paths(self):
        for value in (r"C:\Windows\System32\cmd.exe", r"C:\Apps\PowerShell.EXE", r"C:\a.cmd",
                      r"C:\a.exe:payload", r"C:\..\app.exe", r"\\server\app.exe", r"\\?\C:\app.exe",
                      r"C:app.exe", r"app.exe", "https://example/app.exe", r"C:\a.exe /c calc", None):
            with self.subTest(path=value), self.assertRaises(ValueError):
                windows.validate_app_path(value)
        windows.validate_app_path(r"C:\Program Files\A & B\app.exe")

    def test_lock_native_success_and_failure_without_locking(self):
        function = Mock(return_value=1)
        fake_user32 = Mock(LockWorkStation=function)
        with patch.object(ctypes, "WinDLL", return_value=fake_user32):
            windows.lock_workstation()
            function.assert_called_once_with()
            function.return_value = 0
            with self.assertRaises(windows.LocalActionError):
                windows.lock_workstation()
        self.assertEqual(function.argtypes, [])

    def test_volume_scalar_and_readback_without_changing_hardware(self):
        endpoint = Mock()
        endpoint.GetMasterVolumeLevelScalar.return_value = 0.3
        endpoint.GetMute.return_value = 1
        with patch.object(windows, "_with_volume", side_effect=lambda f: f(endpoint)):
            self.assertEqual(windows.set_volume(30), (30, True))
        endpoint.SetMasterVolumeLevelScalar.assert_called_once_with(0.3, None)
        endpoint.SetMute.assert_not_called()

    def test_volume_bounds_checked_before_opening_audio(self):
        with patch.object(windows, "_with_volume") as audio:
            for value in (-1, 101, 1.5, True, "30"):
                with self.assertRaises(windows.LocalActionError):
                    windows.set_volume(value)
        audio.assert_not_called()

    def test_audio_error_and_readback_mismatch_do_not_claim_success(self):
        with patch.object(windows, "_with_volume", side_effect=OSError("PRIVATE DRIVER ERROR")):
            with self.assertRaises(windows.LocalActionError) as error:
                windows.set_volume(30)
            self.assertNotIn("PRIVATE", str(error.exception))
        endpoint = Mock()
        endpoint.GetMasterVolumeLevelScalar.return_value = 0.9
        with patch.object(windows, "_with_volume", side_effect=lambda f: f(endpoint)):
            with self.assertRaises(windows.LocalActionError):
                windows.set_volume(30)

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_launch_uses_one_fixed_argument_and_no_shell(self):
        with TemporaryDirectory() as folder:
            exe = Path(folder) / "App & Name.exe"
            exe.write_bytes(b"test fixture - not executable")
            with patch.object(windows.subprocess, "Popen") as spawn:
                windows.launch_app(str(exe))
            spawn.assert_called_once_with([str(exe.resolve())], cwd=str(exe.parent), shell=False, close_fds=True)

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_cli_registration_and_upgrade_do_not_start_app(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)
            exe = path / "Fixture.exe"
            exe.write_bytes(b"not executable; registration must not try to run this")
            cmd = [sys.executable, "-m", "xiaoai_pc", "--data-dir", folder]
            def invoke(*args):
                result = subprocess.run(cmd + list(args), capture_output=True, encoding="utf-8", timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result
            invoke("init")
            invoke("add-app", "测试应用", str(exe), "--alias", "测试程序")
            self.assertEqual(json.loads(invoke("test-command", "让电脑打开测试程序").stdout)["code"], "dry_run")
            cfg = load(path / "config.json")
            cfg["commands"] = [c for c in cfg["commands"] if c["action"] not in ("set_volume", "lock")]
            save(path / "config.json", cfg)
            invoke("enable-local-commands")
            self.assertEqual(len(load(path / "config.json")["commands"]), 4)
