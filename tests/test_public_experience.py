from copy import deepcopy
from io import BytesIO
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, MagicMock, patch
import zipfile

import requests
from PIL import Image

from xiaoai_pc import config
from xiaoai_pc.desktop import Desktop
from xiaoai_pc.desktop_model import device_status, friendly_error
from xiaoai_pc import desktop_services as services
from scripts import build


class ConfigRecoveryTests(unittest.TestCase):
    def test_backup_and_external_edit_detection(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            config.save(path, config.DEFAULT_CONFIG)
            initial, content = config.load_snapshot(path)
            changed = deepcopy(initial)
            changed["tts_reply"] = False
            config.save(path, changed, expected_content=content)
            self.assertEqual(path.with_name("config.json.bak").read_bytes(), content)
            saved = path.read_bytes()
            with self.assertRaises(config.ConfigError):
                config.save(path, initial, expected_content=content)
            self.assertEqual(path.read_bytes(), saved)

    def test_failed_atomic_replace_keeps_original_and_unrelated_temp(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            config.save(path, config.DEFAULT_CONFIG)
            original = path.read_bytes()
            unrelated = path.with_suffix(".tmp")
            unrelated.write_bytes(b"user file")
            changed = deepcopy(config.DEFAULT_CONFIG)
            changed["tts_reply"] = False
            replace = Path.replace
            def fail_target(source, target):
                if target == path:
                    raise OSError("simulated disk failure")
                return replace(source, target)
            with patch.object(Path, "replace", fail_target), self.assertRaises(OSError):
                config.save(path, changed)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.with_name("config.json.bak").read_bytes(), original)
            self.assertEqual(unrelated.read_bytes(), b"user file")
            self.assertEqual(list(Path(folder).glob("config.json.*.tmp")), [])

    def test_corrupt_config_is_not_overwritten_or_backed_up(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_bytes(b"broken JSON")
            backup = path.with_name("config.json.bak")
            backup.write_bytes(b"prior backup")
            with self.assertRaises(config.ConfigError):
                config.save(path, config.DEFAULT_CONFIG)
            self.assertEqual(path.read_bytes(), b"broken JSON")
            self.assertEqual(backup.read_bytes(), b"prior backup")


class DesktopFlowTests(unittest.TestCase):
    def make_app(self):
        app = Desktop.__new__(Desktop)
        app.data = deepcopy(config.DEFAULT_CONFIG)
        app.data["xiaomi"]["device_id"] = "old-device"
        app.saved_data = deepcopy(app.data)
        app.prefix = Mock(get=lambda: "让电脑")
        app.poll = Mock(get=lambda: "3")
        app.tts = Mock(get=lambda: True)
        app.auto = Mock(get=lambda: False)
        app.saved_auto = False
        app.devices = MagicMock(current=lambda: -1)
        app.devices_loaded = False
        app.device_ids = []
        app.jobs = Mock(busy=False)
        app.root = Mock()
        app.closing = app.smoke = False
        app.set_status = Mock()
        app.start_job = Mock()
        return app

    def test_empty_refreshed_devices_clear_stale_selection(self):
        app = self.make_app()
        self.assertEqual(app.draft()["xiaomi"]["device_id"], "old-device")
        app.show_devices([])
        self.assertEqual(app.draft()["xiaomi"]["device_id"], "")
        self.assertTrue(app.is_dirty())
        self.assertIn("未找到", device_status([]))

    def test_unsaved_changes_cannot_silently_start_old_configuration(self):
        app = self.make_app()
        self.assertFalse(app.is_dirty())
        app.data["commands"] = []
        app.save_settings = Mock(return_value=False)
        with patch("xiaoai_pc.desktop.messagebox.askokcancel", return_value=False):
            app.start_listener()
        app.start_job.assert_not_called()
        app.save_settings.assert_not_called()
        with patch("xiaoai_pc.desktop.messagebox.askokcancel", return_value=True):
            app.start_listener()
        app.save_settings.assert_called_once()
        app.start_job.assert_not_called()

    def test_exit_cancel_preserves_unsaved_changes_and_job(self):
        app = self.make_app()
        app.data["commands"] = []
        with patch("xiaoai_pc.desktop.messagebox.askyesnocancel", return_value=None):
            app.exit()
        self.assertFalse(app.closing)
        app.jobs.stop.assert_not_called()
        self.assertEqual(app.data["commands"], [])

    def test_preview_never_executes_actions(self):
        app = self.make_app()
        app.tree = Mock()
        app.tree.selection.return_value = ["lock_pc"]
        with patch("xiaoai_pc.windows_actions.lock_workstation") as lock:
            app.preview_command()
        lock.assert_not_called()
        self.assertIn("未执行", app.set_status.call_args.args[0])

    def test_background_error_opens_window(self):
        app = self.make_app()
        app.jobs.events = Queue()
        app.jobs.events.put(("error", "请重新登录"))
        app.show = Mock()
        app.update_buttons = Mock()
        app.pump()
        app.show.assert_called_once()
        app.root.after.assert_called_once()

    def test_specific_network_errors_have_no_remote_payload(self):
        for error in (requests.Timeout("SECRET"), requests.ConnectionError("SECRET"), requests.exceptions.SSLError("SECRET")):
            self.assertNotIn("SECRET", friendly_error(error))
        self.assertIn("超时", friendly_error(requests.Timeout()))
        self.assertIn("证书", friendly_error(requests.exceptions.SSLError()))

    def test_qr_display_accepts_only_bounded_png_before_creating_window(self):
        for image_format, size, accepted in (("PNG", (30, 30), True), ("JPEG", (30, 30), False),
                                             ("PNG", (1025, 10), False)):
            with self.subTest(image_format=image_format, size=size):
                data = BytesIO()
                Image.new("RGB", size, "white").save(data, format=image_format)
                app = self.make_app()
                app.qr_window = app.qr_photo = None
                with patch("xiaoai_pc.desktop.ImageTk.PhotoImage") as photo, \
                     patch("xiaoai_pc.desktop.tk.Toplevel") as window, patch("xiaoai_pc.desktop.ttk.Label"):
                    app.show_qr(data.getvalue())
                    self.assertEqual(photo.called, accepted)
                    self.assertEqual(window.called, accepted)
                self.assertEqual(app.jobs.stop.called, not accepted)

    def test_saved_login_survives_device_list_failure_with_recovery_hint(self):
        import threading
        stop = threading.Event()
        events = []
        qr = Mock(expires_in=30, pass_token="TEST", user_id="TEST", device_id="TEST")
        qr.fetch_qr_image.return_value = b"\x89PNG\r\n\x1a\nfixture"
        qr.poll.return_value = services.CONFIRMED
        account = Mock(token={"passToken": "TEST"})
        with patch.object(services, "XiaomiQrLogin", return_value=qr), patch.object(services, "MiAccount", return_value=account), \
             patch.object(services, "SecretStore") as store, patch.object(services, "MiNA") as mina:
            mina.return_value.device_list.side_effect = requests.Timeout("SECRET")
            services.login(Path("unused"), stop, lambda k, v: events.append((k, v)))
            store.return_value.save.assert_called_once()
        self.assertTrue(any(k == "error" and "登录已保存" in v and "刷新音箱" in v for k, v in events))
        self.assertNotIn("SECRET", str(events))


class PackageTests(unittest.TestCase):
    def test_manifest_excludes_unreviewed_files_from_docs_and_source(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ["src/app.py", "docs/help.md", "docs/private.md", "docs/session.dpapi", "scripts/private.py"]:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fixture", encoding="utf-8")
            (root / "scripts/source-files.txt").write_text("src/app.py\ndocs/help.md\nscripts/source-files.txt\n", encoding="utf-8")
            destination = root / "package"
            build.copy_public_files(destination, root)
            self.assertEqual([p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()], ["docs/help.md"])
            build.write_application_source(root / "source.zip", root)
            with zipfile.ZipFile(root / "source.zip") as archive:
                self.assertEqual(set(archive.namelist()), {"src/app.py", "docs/help.md", "scripts/source-files.txt"})

    def test_manifest_rejects_escape_and_omitted_application_code(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "scripts").mkdir()
            manifest = root / "scripts/source-files.txt"
            manifest.write_text("../private.md", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                build.source_files(root)
            manifest.write_text("scripts/source-files.txt", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src/new.py").write_text("# code", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                build.source_files(root)

    def test_existing_output_is_never_overwritten_or_merged(self):
        with TemporaryDirectory() as folder:
            output = Path(folder)
            portable = output / build.NAME
            portable.mkdir()
            secret = portable / "xiaomi.dpapi"
            secret.write_bytes(b"sentinel, not credentials")
            with patch.object(build, "source_files", return_value=[]), patch.object(build.subprocess, "run") as compiler:
                with self.assertRaises(RuntimeError):
                    build.build(output)
            compiler.assert_not_called()
            self.assertEqual(secret.read_bytes(), b"sentinel, not credentials")
