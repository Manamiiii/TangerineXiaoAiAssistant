from __future__ import annotations

import json
import math
import os
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_CONFIG = {
    "trigger_prefixes": ["让电脑"],
    "xiaomi": {"device_id": ""},
    "poll_interval_seconds": 3,
    "max_command_age_seconds": 30,
    "tts_reply": True,
    "commands": [
        {
            "id": "open_bilibili",
            "action": "open_url",
            "phrases": ["打开B站", "打开哔哩哔哩", "打开哔哩", "打开bilibili"],
            "url": "https://www.bilibili.com",
            "reply": "已请求电脑打开B站",
        }
    ],
}


class ConfigError(ValueError):
    pass


def data_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise ConfigError("需要 Windows LOCALAPPDATA 目录。")
    return Path(base) / "TangerineXiaoAiAssistant"


def normalize(text: str) -> str:
    import unicodedata

    # Only whitespace and edge punctuation are ignored, never interior punctuation.
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(text.split()).strip("，,。.!！?？:：;；")


def validate_url(url: str) -> None:
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
        raise ConfigError("网页地址必须是不含空白的 HTTP/HTTPS URL。")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ConfigError("网页地址格式不正确。") from None
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or "\\" in url):
        raise ConfigError("仅允许配置固定的 HTTP/HTTPS 网页地址，不允许凭据或文件路径。")


def validate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ConfigError("配置根节点必须是 JSON 对象。")
    if set(data) - set(DEFAULT_CONFIG):
        raise ConfigError("配置包含不支持的顶层字段。")
    result = deepcopy(DEFAULT_CONFIG)
    result.update(data)
    prefixes = result["trigger_prefixes"]
    if not isinstance(prefixes, list) or not prefixes or any(
        not isinstance(p, str) or not normalize(p) for p in prefixes
    ):
        raise ConfigError("trigger_prefixes 必须是非空字符串列表。")
    xiaomi = result["xiaomi"]
    if (not isinstance(xiaomi, dict) or set(xiaomi) != {"device_id"}
            or not isinstance(xiaomi["device_id"], str)):
        raise ConfigError("xiaomi 配置只包含字符串 device_id；不要在配置中填写密码。")
    for key, low, high in (("poll_interval_seconds", 2, 60), ("max_command_age_seconds", 5, 120)):
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ConfigError(f"{key} 必须在 {low}–{high} 之间。")
    if not isinstance(result["tts_reply"], bool):
        raise ConfigError("tts_reply 必须是 true 或 false。")
    commands = result["commands"]
    if not isinstance(commands, list):
        raise ConfigError("commands 必须是列表。")
    ids, phrases = set(), set()
    for command in commands:
        if not isinstance(command, dict) or set(command) - {"id", "action", "phrases", "url", "reply"}:
            raise ConfigError("命令包含不支持的字段。")
        cid = command.get("id")
        if not isinstance(cid, str) or not cid or cid in ids:
            raise ConfigError("命令 id 必须非空且唯一。")
        ids.add(cid)
        if command.get("action") != "open_url":
            raise ConfigError("当前 MVP 只支持 open_url，不允许 Shell 命令。")
        validate_url(command.get("url"))
        aliases = command.get("phrases")
        if not isinstance(aliases, list) or not aliases:
            raise ConfigError("每条命令需要非空 phrases 列表。")
        for phrase in aliases:
            if not isinstance(phrase, str) or not normalize(phrase) or normalize(phrase) in phrases:
                raise ConfigError("命令短语必须非空且不能重名。")
            phrases.add(normalize(phrase))
        reply = command.get("reply", "已请求电脑打开网页")
        if not isinstance(reply, str) or len(reply) > 120:
            raise ConfigError("播报内容必须是最多 120 字的固定字符串。")
    return result


def load(path: Path) -> dict:
    try:
        return validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError) as error:
        if isinstance(error, ConfigError):
            raise
        raise ConfigError("配置无法读取，请检查 JSON 格式或先运行 init。") from None


def save(path: Path, data: dict) -> None:
    data = validate(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
