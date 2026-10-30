from __future__ import annotations

from collections import deque
import hashlib
import logging
import threading
import time
from typing import Protocol

from .commands import CommandRouter
from .vendor.voxnode.account import XiaomiAuthError
from .vendor.voxnode.mina import MiNAProtocolError

LOG = logging.getLogger("xiaoai_pc")


class Speaker(Protocol):
    def latest(self) -> list[dict]: ...
    def say(self, text: str) -> bool: ...


def timestamp_ms(value) -> int:
    if isinstance(value, bool):
        return 0
    try:
        stamp = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    # Some firmware versions use seconds rather than milliseconds.
    return stamp * 1000 if 0 < stamp < 100_000_000_000 else stamp


class VoiceGate:
    """Skip initial snapshot; accept fresh, unseen records without logging their text."""
    def __init__(self, *, started_ms: int, max_age_ms: int, capacity: int = 2048):
        self.started_ms = started_ms
        self.max_age_ms = max_age_ms
        self.capacity = capacity
        self.ready = False
        self._seen: set[str] = set()
        self._order: deque[str] = deque()

    def accept(self, records: list[dict], now_ms: int) -> list[str]:
        accepted = []
        for record in sorted(records, key=lambda r: timestamp_ms(r.get("timestamp_ms"))):
            query = record.get("query")
            if not isinstance(query, str) or not query.strip():
                continue
            stamp = timestamp_ms(record.get("timestamp_ms"))
            rid = record.get("request_id")
            key = str(rid) if rid else hashlib.sha256(f"{stamp}:{query}".encode()).hexdigest()
            if key in self._seen:
                continue
            # Remember BEFORE action execution/TTS, including stale/future records.
            self._seen.add(key)
            self._order.append(key)
            while len(self._order) > self.capacity:
                self._seen.discard(self._order.popleft())
            if (self.ready and stamp > self.started_ms
                    and 0 <= now_ms - stamp <= self.max_age_ms):
                accepted.append(query)
        # An empty successful snapshot is also a baseline.
        self.ready = True
        return accepted


class Bridge:
    def __init__(self, speaker: Speaker, router: CommandRouter, config: dict, *,
                 dry_run: bool = False, clock=time.time, stop: threading.Event | None = None,
                 on_state=lambda state: None):
        self.speaker = speaker
        self.router = router
        self.config = config
        self.dry_run = dry_run
        self.clock = clock
        self.stop = stop or threading.Event()
        self.on_state = on_state
        self.gate = VoiceGate(started_ms=int(clock() * 1000),
                              max_age_ms=int(config["max_command_age_seconds"] * 1000))

    def poll_once(self) -> None:
        records = self.speaker.latest()
        if self.stop.is_set():
            return
        was_ready = self.gate.ready
        queries = self.gate.accept(records, int(self.clock() * 1000))
        if not was_ready:
            LOG.info("音箱记录已同步，历史指令已忽略；现在可以说指令。")
        for query in queries:
            if self.stop.is_set():
                return
            result = self.router.execute(query, dry_run=self.dry_run)
            LOG.info("命令结果：%s", result.code)
            if result.reply and self.config["tts_reply"] and not self.dry_run and not self.stop.is_set():
                try:
                    if not self.speaker.say(result.reply):
                        LOG.warning("音箱拒绝播报；电脑动作不会重试。")
                except Exception:
                    LOG.warning("音箱播报失败；电脑动作不会重试。")

    def run(self) -> int:
        failures = 0
        self.on_state("starting")
        LOG.info("语音桥接启动%s。", "（演练模式，不执行或播报）" if self.dry_run else "")
        while not self.stop.is_set():
            try:
                self.poll_once()
                if self.stop.is_set():
                    break
                self.on_state("listening")
                if failures:
                    LOG.info("小米连接已恢复。")
                failures = 0
                wait = self.config["poll_interval_seconds"]
            except XiaomiAuthError:
                self.on_state("auth_required")
                LOG.error("小米授权或登录校验失败，请停止后重新运行 login；没有执行指令。")
                return 3
            except MiNAProtocolError:
                self.on_state("device_error")
                LOG.error("设备选择或对话读取失败；请运行 devices --select 核对音箱，再运行 probe。")
                return 4
            except Exception:
                self.on_state("reconnecting")
                failures += 1
                wait = min(60, self.config["poll_interval_seconds"] * 2 ** min(failures, 5))
                LOG.warning("连接暂不可用，%s 秒后重试（不记录远端响应或凭据）。", wait)
            self.stop.wait(wait)
        self.on_state("stopped")
        return 0
