"""GUI-independent settings and serialized background jobs."""
from copy import deepcopy
import hashlib
from pathlib import Path
import queue
import threading

from . import config
from .windows_actions import validate_app_path
from .secure import SecretStoreError
from .vendor.voxnode.account import XiaomiAuthError
from .vendor.voxnode.mina import MiNAProtocolError


def add_app(data: dict, name: str, path: str) -> dict:
    if not name.strip() or any(c in name for c in "{}\r\n"):
        raise config.ConfigError("请输入有效的应用名称。")
    try:
        validate_app_path(path)
        target = Path(path).resolve(strict=True)
        validate_app_path(str(target))
        if not target.is_file():
            raise OSError
    except ValueError as error:
        raise config.ConfigError(str(error)) from None
    except OSError:
        raise config.ConfigError("所选 EXE 不存在或不可访问。") from None
    result = deepcopy(data)
    cid = "app_" + hashlib.sha256(config.normalize(name).encode()).hexdigest()[:16]
    command = {"id": cid, "action": "launch_app", "phrases": ["打开" + name.strip()],
               "path": str(target), "reply": "已请求启动" + name.strip()}
    result["commands"] = [c for c in result["commands"] if c["id"] != cid] + [command]
    return config.validate(result)


def add_site(data: dict, name: str, url: str) -> dict:
    if not name.strip() or any(c in name for c in "{}\r\n"):
        raise config.ConfigError("请输入有效的网页名称。")
    config.validate_url(url)
    result = deepcopy(data)
    cid = "site_" + hashlib.sha256(config.normalize(name).encode()).hexdigest()[:16]
    command = {"id": cid, "action": "open_url", "phrases": ["打开" + name.strip()],
               "url": url, "reply": "已请求打开" + name.strip()}
    result["commands"] = [c for c in result["commands"] if c["id"] != cid] + [command]
    return config.validate(result)


class Jobs:
    """Only one listener/login/probe at a time. UI events contain no credentials."""
    def __init__(self):
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.thread = None
        self.name = ""

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def emit(self, kind: str, value=None):
        self.events.put((kind, value))

    def start(self, name: str, work) -> bool:
        if self.busy:
            return False
        self.cancel = threading.Event()
        self.name = name
        def target():
            try:
                work(self.cancel, self.emit)
            except (config.ConfigError, SecretStoreError, XiaomiAuthError, MiNAProtocolError) as error:
                self.emit("error", str(error))
            except Exception:
                self.emit("error", "操作未完成，请检查网络、登录状态和音箱选择。")
            finally:
                self.emit("finished", name)
        self.thread = threading.Thread(target=target, name="xiaoai-" + name, daemon=False)
        self.thread.start()
        return True

    def stop(self):
        self.cancel.set()
