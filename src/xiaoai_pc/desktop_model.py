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
from .vendor.voxnode.account import XiaomiServiceError
from .vendor.voxnode.qrlogin import QrLoginError
import requests


def selectable_devices(devices):
    return [d for d in devices if isinstance(d, dict) and d.get("deviceID") and d.get("hardware")]


def device_status(devices):
    count = len(selectable_devices(devices))
    if not count:
        return "未找到可选音箱。请确认登录的是绑定音箱的小米账号；可重新扫码或稍后刷新音箱。"
    return f"找到 {count} 台音箱，请选择后保存设置，再检查连接"


def friendly_error(error):
    if isinstance(error, (config.ConfigError, SecretStoreError, XiaomiAuthError, MiNAProtocolError,
                          XiaomiServiceError, QrLoginError)):
        return str(error)
    if isinstance(error, requests.exceptions.SSLError):
        return "安全连接验证失败。请检查系统日期、代理和网络后重试；不要关闭证书验证。"
    if isinstance(error, requests.Timeout):
        return "连接超时，请检查网络后重试；尚未完成的扫码可重新发起。"
    if isinstance(error, requests.RequestException):
        return "无法连接小米服务，请检查网络或代理后重试。"
    return "操作未完成，请检查网络、登录状态和音箱选择。"


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
            except Exception as error:
                self.emit("error", friendly_error(error))
            finally:
                self.emit("finished", name)
        self.thread = threading.Thread(target=target, name="xiaoai-" + name, daemon=False)
        self.thread.start()
        return True

    def stop(self):
        self.cancel.set()
