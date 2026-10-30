import unittest
from unittest.mock import patch
from copy import deepcopy

from xiaoai_pc.config import ConfigError, DEFAULT_CONFIG, validate
from xiaoai_pc.commands import CommandRouter, open_url


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.config = validate(deepcopy(DEFAULT_CONFIG))
        self.router = CommandRouter(self.config)

    def test_voice_variants(self):
        for text in ("让电脑打开B站", "小爱同学，让电脑打开 B 站。", "让电脑打开哔哩哔哩", "让电脑打开Ｂ站"):
            with self.subTest(text=text):
                self.assertEqual(self.router.match(text)["id"], "open_bilibili")

    def test_whole_phrase_and_trigger_are_required(self):
        for text in ("打开B站", "不要让电脑打开B站", "让电脑不要打开B站", "让电脑打开B站然后关机",
                     "让电脑打开https://evil.example", "让电脑打开B站 & calc", "让电脑打开微信", "让电脑关机"):
            with self.subTest(text=text):
                self.assertIsNone(self.router.match(text))

    def test_dry_run_does_not_open_browser(self):
        with patch("webbrowser.open") as browser:
            self.assertTrue(self.router.execute("让电脑打开B站", dry_run=True).ok)
        browser.assert_not_called()

    def test_execution_uses_only_configured_url(self):
        with patch("webbrowser.open", return_value=True) as browser:
            result = self.router.execute("小爱同学，让电脑打开B站")
        self.assertEqual(result.code, "browser_requested")
        browser.assert_called_once_with("https://www.bilibili.com", new=2)

    def test_failure_is_not_success_or_exception_text(self):
        with patch("webbrowser.open", side_effect=RuntimeError("SECRET")):
            result = self.router.execute("让电脑打开B站")
        self.assertFalse(result.ok)
        self.assertNotIn("SECRET", result.reply)
        with patch("webbrowser.open", return_value=False):
            self.assertFalse(self.router.execute("让电脑打开B站").ok)

    def test_new_alias_and_site_by_configuration(self):
        self.config["commands"].append({"id": "docs", "action": "open_url", "phrases": ["打开文档"], "url": "https://docs.python.org"})
        router = CommandRouter(validate(self.config))
        with patch("webbrowser.open", return_value=True) as browser:
            self.assertTrue(router.execute("让电脑打开文档").ok)
        browser.assert_called_once_with("https://docs.python.org", new=2)

    def test_reject_unsafe_or_ambiguous_configuration(self):
        for url in ("file:///C:/Windows/system32/cmd.exe", "javascript:alert(1)", "https://u:p@example.com",
                    "https://example.com\n", "https://", "https://x:wrong", "https://x\\y"):
            cfg = deepcopy(self.config)
            cfg["commands"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(ConfigError):
                validate(cfg)
        for key, value in (("action", "shell"), ("phrases", ["打开B站", "打开b站"])):
            cfg = deepcopy(self.config)
            cfg["commands"][0][key] = value
            with self.assertRaises(ConfigError):
                validate(cfg)
        for key, value in (("poll_interval_seconds", 0), ("poll_interval_seconds", float("nan")),
                           ("trigger_prefixes", [""]), ("tts_reply", "false")):
            cfg = deepcopy(self.config)
            cfg[key] = value
            with self.assertRaises(ConfigError):
                validate(cfg)
