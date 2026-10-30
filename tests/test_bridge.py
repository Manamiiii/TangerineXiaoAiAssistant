from copy import deepcopy
import unittest
import threading
from unittest.mock import Mock

from xiaoai_pc.bridge import Bridge, VoiceGate, timestamp_ms
from xiaoai_pc.commands import CommandRouter, Result
from xiaoai_pc.config import DEFAULT_CONFIG
from xiaoai_pc.vendor.voxnode.account import XiaomiAuthError

BASE = 1_800_000_000_000


def message(offset=1000, rid="one", query="让电脑打开B站"):
    return {"timestamp_ms": BASE + offset, "request_id": rid, "query": query}


class GateTests(unittest.TestCase):
    def setUp(self):
        self.gate = VoiceGate(started_ms=BASE, max_age_ms=30_000)

    def test_initial_history_skipped(self):
        self.assertEqual(self.gate.accept([message(-1000)], BASE), [])
        self.assertEqual(self.gate.accept([message(-1000), message(1000, "new")], BASE + 2000), ["让电脑打开B站"])

    def test_empty_initial_snapshot_does_not_drop_first_command(self):
        self.gate.accept([], BASE)
        self.assertEqual(len(self.gate.accept([message()], BASE + 1000)), 1)

    def test_duplicate_ids_same_timestamps_out_of_order_and_missing_id(self):
        self.gate.accept([], BASE)
        records = [message(2000, "two"), message(1000, "one"), message(1000, "three"), message(3000, "")]
        self.assertEqual(len(self.gate.accept(records, BASE + 4000)), 4)
        self.assertEqual(self.gate.accept(list(reversed(records)), BASE + 5000), [])

    def test_stale_future_and_pre_start_records_never_execute(self):
        self.gate.accept([], BASE)
        self.assertEqual(self.gate.accept([message(-1, "old"), message(1000, "stale"), message(100_000, "future")], BASE + 40_000), [])
        self.assertEqual(timestamp_ms((BASE + 1000) // 1000), BASE + 1000)
        for value in (None, "bad", float("inf"), True):
            self.assertEqual(timestamp_ms(value), 0)


class BridgeTests(unittest.TestCase):
    def make_bridge(self):
        self.config = deepcopy(DEFAULT_CONFIG)
        self.speaker = Mock()
        self.speaker.latest.return_value = []
        self.handler = Mock(return_value=Result(True, "browser_requested", "已请求打开网页"))
        self.now = BASE / 1000
        self.stop = Mock()
        self.stop.is_set.return_value = False
        def wait(_):
            if self.stop.wait.call_count >= 2:
                self.stop.is_set.return_value = True
        self.stop.wait.side_effect = wait
        bridge = Bridge(self.speaker, CommandRouter(self.config, {"open_url": self.handler}), self.config,
                        clock=lambda: self.now, stop=self.stop)
        return bridge

    def test_tts_failure_never_reexecutes(self):
        bridge = self.make_bridge()
        bridge.poll_once()
        self.now += 2
        self.speaker.latest.return_value = [message()]
        self.speaker.say.side_effect = RuntimeError("SECRET TOKEN")
        with self.assertLogs("xiaoai_pc") as logs:
            bridge.poll_once()
            bridge.poll_once()
        self.handler.assert_called_once()
        self.assertNotIn("SECRET", "".join(logs.output))
        self.assertNotIn("让电脑", "".join(logs.output))

    def test_transient_failure_reconnects_with_backoff(self):
        bridge = self.make_bridge()
        self.speaker.latest.side_effect = [OSError("secret network response"), []]
        with self.assertLogs("xiaoai_pc") as logs:
            self.assertEqual(bridge.run(), 0)
        self.assertEqual(self.stop.wait.call_args_list[0].args, (6,))
        self.assertEqual(self.stop.wait.call_args_list[1].args, (3,))
        self.assertTrue(bridge.gate.ready)
        self.assertNotIn("secret", "".join(logs.output))

    def test_auth_failure_stops_with_login_instruction(self):
        bridge = self.make_bridge()
        self.speaker.latest.side_effect = XiaomiAuthError("SECRET")
        with self.assertLogs("xiaoai_pc") as logs:
            self.assertEqual(bridge.run(), 3)
        self.assertIn("login", "".join(logs.output))
        self.assertNotIn("SECRET", "".join(logs.output))

    def test_dry_run_no_action_or_tts(self):
        bridge = self.make_bridge()
        bridge.dry_run = True
        bridge.poll_once()
        self.now += 2
        self.speaker.latest.return_value = [message()]
        bridge.poll_once()
        self.handler.assert_not_called()
        self.speaker.say.assert_not_called()

    def test_stop_during_network_read_does_not_execute_returned_command(self):
        bridge = self.make_bridge()
        bridge.stop = threading.Event()
        bridge.poll_once()
        self.now += 2
        def latest():
            bridge.stop.set()
            return [message()]
        self.speaker.latest.side_effect = latest
        bridge.poll_once()
        self.handler.assert_not_called()
        self.speaker.say.assert_not_called()
