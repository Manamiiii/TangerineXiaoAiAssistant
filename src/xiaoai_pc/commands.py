from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import webbrowser

from .config import normalize, validate_url
from .rules import parse_level, volume_pattern
from . import windows_actions


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


def launch_app(command: dict) -> Result:
    windows_actions.launch_app(command["path"])
    return Result(True, "app_requested", command.get("reply", "已请求启动应用"))


def set_volume(command: dict) -> Result:
    actual, muted = windows_actions.set_volume(command["level"])
    reply = f"系统音量已设置为百分之{actual}"
    if muted:
        reply += "，当前仍为静音"
    return Result(True, "volume_set", reply)


def lock_pc(command: dict) -> Result:
    windows_actions.lock_workstation()
    return Result(True, "lock_requested", "已请求电脑锁屏")


class CommandRouter:
    def __init__(self, config: dict, handlers: dict[str, Callable[[dict], Result]] | None = None):
        self.prefixes = sorted((normalize(p) for p in config["trigger_prefixes"]), key=len, reverse=True)
        self.commands = {normalize(p): c for c in config["commands"] if c["action"] != "set_volume" for p in c["phrases"]}
        self.volume_rules = [(volume_pattern(normalize(p)), c) for c in config["commands"]
                             if c["action"] == "set_volume" for p in c["phrases"]]
        self.handlers = handlers if handlers is not None else {
            "open_url": open_url, "launch_app": launch_app, "set_volume": set_volume, "lock": lock_pc,
        }

    def match(self, query: str) -> dict | None:
        text = normalize(query)
        if text.startswith("小爱同学"):
            text = text[len("小爱同学"):].lstrip("，,。.!！?？:：")
        for prefix in self.prefixes:
            if text.startswith(prefix):
                body = text[len(prefix):].lstrip("，,:：")
                matches = [self.commands[body]] if body in self.commands else []
                for pattern, rule in self.volume_rules:
                    match = pattern.fullmatch(body)
                    if match and (level := parse_level(match["level"])) is not None:
                        matches.append({**rule, "level": level})
                # Ambiguous configuration must not choose an arbitrary action.
                return matches[0] if len(matches) == 1 else None
        return None

    def execute(self, query: str, *, dry_run: bool = False) -> Result:
        command = self.match(query)
        if command is None:
            return Result(False, "unmatched")
        handler = self.handlers.get(command["action"])
        if handler is None:
            return Result(False, "unsupported_action", "该命令尚未启用")
        if dry_run:
            return Result(True, "dry_run", "演练：已匹配命令，未执行")
        try:
            return handler(command)
        except windows_actions.LocalActionError as error:
            return Result(False, "execution_failed", str(error))
        except Exception:
            # Neither arbitrary OS exceptions nor user text enter logs/TTS.
            return Result(False, "execution_failed", "电脑执行失败，请查看本地状态")
