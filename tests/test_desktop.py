from copy import deepcopy
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch, MagicMock

from xiaoai_pc import config, startup, desktop_services as services
from xiaoai_pc.desktop_model import Jobs, add_app, add_site


class SettingsTests(unittest.TestCase):
    def test_site_is_fixed_and_original_untouched(self):
        data = deepcopy(config.DEFAULT_CONFIG)
        result = add_site(data, "文档", "https://example.com/docs")
        self.assertEqual(len(data["commands"]), 3)
        self.assertEqual(result["commands"][-1]["url"], "https://example.com/docs")
        updated = add_site(result, "文档", "https://example.com/new")
        self.assertEqual(len(updated["commands"]), 4)
        self.assertEqual(updated["commands"][-1]["url"], "https://example.com/new")

    def test_invalid_site_and_conflicting_alias_rejected(self):
        for name, url in [("下载", "file:///C:/Windows"), ("B站", "https://example.com"),
                          ("{level}", "https://example.com"), ("", "https://example.com")]:
            with self.subTest(name=name), self.assertRaises(config.ConfigError):
                add_site(config.DEFAULT_CONFIG, name, url)

    def test_app_registration_does_not_execute_and_checks_file(self):
        with tempfile.TemporaryDirectory() as folder, patch("subprocess.Popen") as spawn:
            path = Path(folder) / "sample.exe"
            path.write_bytes(b"fixture, not a program")
            result = add_app(config.DEFAULT_CONFIG, "播放器", str(path))
            self.assertEqual(result["commands"][-1]["path"], str(path))
            spawn.assert_not_called()
            for bad in [str(Path(folder) / "missing.exe"), str(Path(folder) / "cmd.exe")]:
                with self.assertRaises(config.ConfigError):
                    add_app(config.DEFAULT_CONFIG, "应用", bad)


class JobTests(unittest.TestCase):
    def test_serializes_stops_and_can_restart(self):
        jobs = Jobs()
        started = threading.Event()
        def worker(stop, emit):
            started.set()
            stop.wait(2)
        try:
            self.assertTrue(jobs.start("listen", worker))
            self.assertTrue(started.wait(2))
            self.assertFalse(jobs.start("login", Mock()))
        finally:
            jobs.stop()
            jobs.thread.join(3)
        self.assertFalse(jobs.busy)
        self.assertTrue(jobs.start("again", lambda stop, emit: emit("status", stop.is_set())))
        jobs.thread.join(3)
        self.assertIn(("status", False), list(jobs.events.queue))

    def test_unknown_error_text_not_exposed(self):
        jobs = Jobs()
        jobs.start("test", Mock(side_effect=OSError("SECRET_TOKEN raw response")))
        jobs.thread.join(3)
        events = list(jobs.events.queue)
        self.assertNotIn("SECRET_TOKEN", str(events))
        self.assertTrue(any(kind == "error" for kind, _ in events))
        self.assertIn(("finished", "test"), events)


class StartupTests(unittest.TestCase):
    def test_default_off_no_registry_write(self):
        with patch.object(startup, "read", return_value=None), patch.object(startup.winreg, "CreateKeyEx") as create:
            startup.set_enabled(False, Path("D:/data"), Path("D:/data/config.json"))
            create.assert_not_called()

    def test_only_own_current_user_run_value_is_changed(self):
        key = MagicMock()
        with patch.object(startup, "read", return_value=None), patch.object(startup, "command_line", return_value="quoted command"), \
             patch.object(startup.winreg, "CreateKeyEx", return_value=key) as create, \
             patch.object(startup.winreg, "SetValueEx") as write:
            startup.set_enabled(True, Path("D:/data"), Path("D:/data/config.json"))
            create.assert_called_once_with(startup.winreg.HKEY_CURRENT_USER, startup.RUN_KEY, 0, startup.winreg.KEY_SET_VALUE)
            write.assert_called_once_with(key.__enter__.return_value, startup.VALUE_NAME, 0, startup.winreg.REG_SZ, "quoted command")
        with patch.object(startup, "read", return_value="old command"), \
             patch.object(startup.winreg, "CreateKeyEx", return_value=key), patch.object(startup.winreg, "DeleteValue") as delete:
            startup.set_enabled(False, Path("D:/data"), Path("D:/data/config.json"))
            delete.assert_called_once_with(key.__enter__.return_value, startup.VALUE_NAME)

    def test_frozen_command_quotes_custom_paths(self):
        with patch.object(startup.sys, "frozen", True, create=True), \
             patch.object(startup.sys, "executable", "D:/My Tools/TangerineXiaoAiAssistant.exe"), \
             patch.object(Path, "is_file", return_value=True):
            folder = Path("D:/Test Data")
            cfg = folder / "custom config.json"
            expected = subprocess.list2cmdline(["D:\\My Tools\\TangerineXiaoAiAssistant-Desktop.exe", "--data-dir", str(folder.resolve()),
                                               "--config", str(cfg.resolve()), "desktop", "--hidden"])
            self.assertEqual(startup.command_line(folder, cfg), expected)

    def test_missing_executable_or_long_path_rejected(self):
        with patch.object(Path, "is_file", return_value=False), self.assertRaises(RuntimeError):
            startup.command_line(Path("D:/data"), Path("D:/data/config.json"))
        with patch.object(Path, "is_file", return_value=True), self.assertRaises(RuntimeError):
            folder = Path("D:/" + "long/" * 60)
            startup.command_line(folder, folder / "config.json")


class DesktopServiceTests(unittest.TestCase):
    def setUp(self):
        self.stop = threading.Event()
        self.events = []
        self.emit = lambda kind, value: self.events.append((kind, value))
        self.qr = Mock(expires_in=30, pass_token="SECRET", user_id="PRIVATE", device_id="PRIVATE")
        self.qr.fetch_qr_image.return_value = b"\x89PNG\r\n\x1a\nfixture"
        self.qr.poll.return_value = services.CONFIRMED
        self.account = Mock(token={"passToken": "SECRET"})
        for name, value in [("XiaomiQrLogin", self.qr), ("MiAccount", self.account)]:
            p = patch.object(services, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_cancel_after_token_exchange_preserves_previous_login(self):
        self.account.login_with_pass_token.side_effect = lambda *args: self.stop.set()
        with patch.object(services, "SecretStore") as store:
            services.login(Path("unused"), self.stop, self.emit)
            store.assert_not_called()
        self.assertEqual(self.account.token, {})
        self.assertEqual(self.events[-1], ("qr", None))
        self.assertNotIn("SECRET", str(self.events))
        self.qr._session.close.assert_called_once()

    def test_cancel_during_initial_request_skips_qr(self):
        self.qr.start.side_effect = self.stop.set
        services.login(Path("unused"), self.stop, self.emit)
        self.qr.fetch_qr_image.assert_not_called()
        self.account.login_with_pass_token.assert_not_called()

    def test_success_uses_encrypted_store_not_plaintext_cache(self):
        with patch.object(services, "SecretStore") as store, patch.object(services, "MiNA") as mina:
            mina.return_value.device_list.return_value = [{"deviceID": "d", "hardware": "LX06"}]
            services.login(Path("test"), self.stop, self.emit)
            store.assert_called_once_with(Path("test/xiaomi.dpapi"))
            store.return_value.save.assert_called_once()
        self.assertIn(("devices", [{"deviceID": "d", "hardware": "LX06"}]), self.events)
        self.assertNotIn("SECRET", str(self.events))

    def test_bad_qr_is_rejected_and_closed(self):
        self.qr.fetch_qr_image.return_value = b"not PNG"
        with self.assertRaises(config.ConfigError):
            services.login(Path("unused"), self.stop, self.emit)
        self.account._session.close.assert_called_once()
        self.account.login_with_pass_token.assert_not_called()

    def test_missing_device_requires_selection_before_network(self):
        with patch.object(services, "SecureAccount") as account:
            for operation in (services.listen, services.probe):
                with self.assertRaises(config.ConfigError):
                    operation(Path("unused"), config.DEFAULT_CONFIG, self.stop, self.emit)
            account.assert_not_called()
