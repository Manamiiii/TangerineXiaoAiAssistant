"""Finite numeric grammar for volume; no general natural language evaluation."""
import re

LEVEL_PATTERN = r"(?:百分之)?(?:[0-9]{1,3}|[零〇一二两三四五六七八九十百]{1,4})%?"
DIGITS = {char: i for i, char in enumerate("零一二三四五六七八九")}
DIGITS.update({"〇": 0, "两": 2})


def parse_level(text: str) -> int | None:
    if text.startswith("百分之"):
        if text.endswith("%"):
            return None
        text = text[3:]
    elif text.endswith("%"):
        text = text[:-1]
    if re.fullmatch(r"[0-9]{1,3}", text):
        value = int(text)
    elif text in DIGITS:
        value = DIGITS[text]
    elif text in ("一百", "百"):
        value = 100
    elif re.fullmatch(r"[一二三四五六七八九]?十[一二三四五六七八九]?", text):
        tens, units = text.split("十")
        value = DIGITS.get(tens, 1) * 10 + DIGITS.get(units, 0)
    else:
        return None
    return value if 0 <= value <= 100 else None


def volume_pattern(phrase: str) -> re.Pattern:
    before, after = phrase.split("{level}")
    return re.compile(re.escape(before) + f"(?P<level>{LEVEL_PATTERN})" + re.escape(after))
