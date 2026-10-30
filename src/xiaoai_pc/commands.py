from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import webbrowser

from .config import normalize, validate_url


@dataclass(frozen=True)
class Result:
    ok: bool
    code: str
    reply: str = ""


def open_url(command: dict) -> Result:
    # Defense in depth: execution never uses a URL extracted from voice input.
    validate_url(command["url"])
    if not webbrowser.open(command["url"], new=2):
        return Result(False, "browser_failed", "电脑未能启动浏览器")
    return Result(True, "browser_requested", command.get("reply", "已请求电脑打开网页"))


class CommandRouter:
    def __init__(self, config: dict, handlers: dict[str, Callable[[dict], Result]] | None = None):
        self.prefixes = sorted((normalize(p) for p in config["trigger_prefixes"]), key=len, reverse=True)
        self.commands = {normalize(p): c for c in config["commands"] for p in c["phrases"]}
        self.handlers = handlers if handlers is not None else {"open_url": open_url}

    def match(self, query: str) -> dict | None:
        text = normalize(query)
        if text.startswith("小爱同学"):
            text = text[len("小爱同学"):].lstrip("，,。.!！?？:：")
        for prefix in self.prefixes:
            if text.startswith(prefix):
                return self.commands.get(text[len(prefix):].lstrip("，,:："))
        return None

    def execute(self, query: str, *, dry_run: bool = False) -> Result:
        command = self.match(query)
        if command is None:
            return Result(False, "unmatched")
        handler = self.handlers.get(command["action"])
        if handler is None:
            return Result(False, "unsupported_action", "该命令尚未启用")
        if dry_run:
            return Result(True, "dry_run", "演练：已匹配网页命令，未执行")
        try:
            return handler(command)
        except Exception:
            # Neither arbitrary OS exceptions nor user text enter logs/TTS.
            return Result(False, "execution_failed", "电脑执行失败，请查看本地状态")
