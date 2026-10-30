import json
from pathlib import Path
import unittest
from unittest.mock import Mock

import requests

from xiaoai_pc.vendor.voxnode.account import MiAccount, SID_MINA, XiaomiAuthError, _parse_resp
from xiaoai_pc.vendor.voxnode.mina import MiNA, MiNAProtocolError
from xiaoai_pc.xiaomi import SecureAccount, XiaomiSpeaker


def response(info):
    return {"code": 0, "data": {"code": 0, "info": json.dumps(info)}}


class XiaomiTests(unittest.TestCase):
    def test_speaker_retries_initial_device_validation_after_outage(self):
        speaker = XiaomiSpeaker(Mock(), "speaker-id")
        speaker.mina = Mock()
        speaker.mina.device_list.side_effect = [requests.ConnectionError(), [{"deviceID": "speaker-id"}]]
        speaker.mina.latest_asks.return_value = []
        with self.assertRaises(requests.ConnectionError):
            speaker.latest()
        self.assertEqual(speaker.latest(), [])
        self.assertEqual(speaker.latest(), [])
        self.assertEqual(speaker.mina.device_list.call_count, 2)

    def test_wrong_device_never_fetches_or_speaks(self):
        speaker = XiaomiSpeaker(Mock(), "wrong-id")
        speaker.mina = Mock()
        speaker.mina.device_list.return_value = [{"deviceID": "actual-id"}]
        with self.assertRaises(MiNAProtocolError):
            speaker.latest()
        with self.assertRaises(MiNAProtocolError):
            speaker.say("测试")
        speaker.mina.latest_asks.assert_not_called()
        speaker.mina.tts.assert_not_called()

    def test_record_from_upstream_shape(self):
        account = Mock()
        nlp = {"meta": {"timestamp": 1_800_000_001_000, "request_id": "voice-1"},
               "response": {"answer": [{"intention": {"query": "让电脑打开B站"}, "content": "好的"}]}}
        account.request.return_value = response({"result": [{"nlp": json.dumps(nlp)}]})
        messages = MiNA(account).latest_asks("speaker-id")
        self.assertEqual(messages[0]["query"], "让电脑打开B站")
        self.assertEqual(messages[0]["timestamp_ms"], 1_800_000_001_000)
        call = account.request.call_args
        self.assertEqual(call.args[0], "https://api2.mina.mi.com/remote/ubus")
        self.assertEqual(call.kwargs["data"]["method"], "nlp_result_get")

    def test_empty_success_distinct_from_transport_or_protocol_failure(self):
        account = Mock()
        mina = MiNA(account)
        account.request.return_value = response({"result": []})
        self.assertEqual(mina.latest_asks("id"), [])
        account.request.side_effect = requests.Timeout()
        with self.assertRaises(requests.Timeout):
            mina.latest_asks("id")
        account.request.side_effect = None
        for result in ({"code": 0, "data": {"code": -1}}, response({}), response({"result": [None]}), response({"result": "bad"})):
            account.request.return_value = result
            with self.assertRaises(MiNAProtocolError):
                mina.latest_asks("id")

    def test_tts_checks_inner_status(self):
        account = Mock()
        account.request.return_value = {"code": 0, "data": {"code": -1}}
        self.assertFalse(MiNA(account).tts("id", "测试"))

    def test_401_keeps_pass_token_for_one_refresh(self):
        account = MiAccount("", "")
        account.token = {"userId": "user", "deviceId": "dev", "passToken": "PASS", SID_MINA: ["SEC", "OLD"]}
        first, second = Mock(status_code=401), Mock(status_code=200)
        second.json.return_value = {"code": 0, "data": []}
        account._session = Mock()
        account._session.request.side_effect = [first, second]
        def renew(sid):
            self.assertEqual(account.token["passToken"], "PASS")
            account.token[sid] = ["SEC", "NEW"]
            return True
        account.login = Mock(side_effect=renew)
        self.assertEqual(account.request("https://api2.mina.mi.com/test"), {"code": 0, "data": []})
        account.login.assert_called_once_with(SID_MINA)
        self.assertEqual(account._session.request.call_count, 2)

    def test_no_infinite_auth_retry(self):
        account = MiAccount("", "")
        account.token = {"userId": "user", "deviceId": "dev", "passToken": "PASS", SID_MINA: ["s", "t"]}
        account._session = Mock()
        account._session.request.return_value = Mock(status_code=401)
        def renew(sid):
            account.token[sid] = ["s", "new"]
            return True
        account.login = Mock(side_effect=renew)
        with self.assertRaises(XiaomiAuthError):
            account.request("https://api2.mina.mi.com/test")
        self.assertEqual(account._session.request.call_count, 2)

    def test_plaintext_store_disabled_and_parser_redacted(self):
        with self.assertRaises(ValueError):
            MiAccount("", "", token_path=Path("would-leak.json"))
        with self.assertRaises(XiaomiAuthError) as error:
            _parse_resp("SECRET_TOKEN non-json")
        self.assertNotIn("SECRET_TOKEN", str(error.exception))

    def test_secure_account_can_replace_unreadable_cache(self):
        store = Mock()
        store.load.side_effect = RuntimeError("broken")
        account = SecureAccount(store, load_existing=False)
        self.assertEqual(account.token, {})
        store.load.assert_not_called()
        account._save_token({"passToken": "test"})
        store.save.assert_called_once_with({"passToken": "test"})
        account.close()
