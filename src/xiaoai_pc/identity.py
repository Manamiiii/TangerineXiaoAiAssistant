"""Stable product identity; fixture identities are baked into separate test builds."""
from pathlib import Path
import json
import re
import sys
import uuid

PRODUCTION = {
    "app_id": "io.github.Manamiiii.TangerineXiaoAiAssistant",
    "guid": "{B498FC4D-8B2D-54A7-83A5-F0DF945A1C4C}",
    "display_name": "橘子小爱电脑助手",
    "directory_name": "TangerineXiaoAiAssistant",
    "data_folder": "TangerineXiaoAiAssistant",
    "startup_value": "TangerineXiaoAiAssistant",
    "fixture": False,
}


def fixture_identity(identifier):
    identifier = str(uuid.UUID(identifier))
    if uuid.UUID(identifier) == uuid.UUID(PRODUCTION["guid"]):
        raise ValueError("Fixture GUID must differ from the production GUID")
    folder = "TangerineXiaoAiAssistant-InstallerFixture-" + identifier
    return {"app_id": PRODUCTION["app_id"] + ".fixture." + identifier,
            "guid": "{" + identifier.upper() + "}",
            "display_name": "XiaoAI Installer Fixture " + identifier[:8],
            "directory_name": folder, "data_folder": folder, "startup_value": folder,
            "fixture": True}


def validate(value):
    if value == PRODUCTION:
        return dict(value)
    try:
        expected = fixture_identity(value["guid"].strip("{}"))
    except (ValueError, KeyError, AttributeError, TypeError):
        raise RuntimeError("应用身份无效，请重新下载完整程序。") from None
    if value != expected or not re.fullmatch(r"[A-Za-z0-9.-]+", value["data_folder"]):
        raise RuntimeError("应用身份无效，请重新下载完整程序。")
    return expected


def load():
    if getattr(sys, "frozen", False):
        try:
            return validate(json.loads((Path(sys._MEIPASS) / "app-identity.json").read_text("utf-8")))
        except (OSError, ValueError):
            raise RuntimeError("应用身份缺失，请重新下载完整程序。") from None
    return dict(PRODUCTION)


IDENTITY = load()
