"""MiNA（小爱音箱）客户端：设备列表 / TTS / 最新对话轮询。"""
from __future__ import annotations

import json
import random
import string
from typing import Optional

from .account import MiAccount, UA_MINA


class MiNAProtocolError(RuntimeError):
    pass

MINA_BASE = "https://api2.mina.mi.com"


def _request_id() -> str:
    return "app_ios_" + "".join(random.choices(string.ascii_letters + string.digits, k=30))


class MiNA:
    def __init__(self, account: MiAccount):
        self.account = account

    # ------------------------------------------------------------------
    def _get(self, uri: str) -> dict:
        return self.account.request(MINA_BASE + uri + "&requestId=" + _request_id(),
                                    headers={"User-Agent": UA_MINA})

    def _post(self, uri: str, data: dict) -> dict:
        data["requestId"] = _request_id()
        return self.account.request(MINA_BASE + uri, data=data, headers={"User-Agent": UA_MINA})

    def _ubus(self, device_id: str, method: str, path: str, message: dict) -> dict:
        return self._post("/remote/ubus", {
            "deviceId": device_id,
            "message": json.dumps(message),
            "method": method,
            "path": path,
        })

    # ------------------------------------------------------------------
    def device_list(self) -> list[dict]:
        result = self._get("/admin/v2/device_list?master=0")
        data = result.get("data")
        if not isinstance(data, list) or any(not isinstance(d, dict) for d in data):
            raise MiNAProtocolError("设备列表结构不正确")
        return data

    def tts(self, device_id: str, text: str) -> bool:
        res = self._ubus(device_id, "text_to_speech", "mibrain", {"text": text})
        data = res.get("data")
        return res.get("code") == 0 and (not isinstance(data, dict) or data.get("code", 0) == 0)

    def latest_asks(self, device_id: str) -> list[dict]:
        """获取音箱最近几轮对话，返回 [{request_id, timestamp_ms, query, answer}]。

        对应 MiService 的 nlp_result_get ubus 调用
        （MIT，© 2021-2026 Yonsm，https://github.com/Yonsm/MiService）。
        """
        out: list[dict] = []
        res = self._ubus(device_id, "nlp_result_get", "mibrain", {})
        data = res.get("data") or {}
        if not isinstance(data, dict) or data.get("code") != 0:
            raise MiNAProtocolError("音箱对话接口失败，设备可能不支持 nlp_result_get")
        try:
            info = json.loads(data["info"])
            items = info["result"]
            if not isinstance(items, list):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise MiNAProtocolError("音箱对话响应结构不正确") from None
        malformed = 0
        for item in items:
            if not isinstance(item, dict) or "nlp" not in item:
                malformed += 1
                continue
            try:
                nlp = json.loads(item["nlp"])
                meta = nlp.get("meta", {})
                answers = nlp.get("response", {}).get("answer", [])
                query = ""
                if answers:
                    first = answers[0]
                    intention = first.get("intention") or {}
                    if isinstance(intention, dict):
                        query = intention.get("query", "")
                out.append({
                    "request_id": str(meta.get("request_id", "")),
                    "timestamp_ms": int(meta.get("timestamp", 0)),
                    "query": query,
                    "answer": str(answers[0].get("content", "")) if answers else "",
                })
            except (ValueError, TypeError, KeyError, AttributeError, IndexError):
                malformed += 1
                continue
        if items and malformed == len(items):
            raise MiNAProtocolError("音箱对话记录无法解析")
        return out

    @staticmethod
    def pick_speaker(devices: list[dict]) -> Optional[dict]:
        """从设备列表中选出第一个支持云 TTS 的小爱设备。"""
        for d in devices:
            caps = d.get("capabilities") or {}
            if isinstance(caps, str):
                try:
                    caps = json.loads(caps)
                except json.JSONDecodeError:
                    caps = {}
            if d.get("hardware") and d.get("deviceID"):
                return d
        return None
