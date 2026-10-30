"""Cancellable desktop operations using the same Xiaomi adapter as the CLI."""
import time

from . import config
from .bridge import Bridge
from .commands import CommandRouter
from .secure import SecretStore
from .vendor.voxnode.account import MiAccount, SID_MINA
from .vendor.voxnode.mina import MiNA
from .vendor.voxnode.qrlogin import XiaomiQrLogin, CONFIRMED, SCANNED, EXPIRED, FAILED
from .xiaomi import SecureAccount, XiaomiSpeaker, require_login


def login(directory, stop, emit):
    qr = XiaomiQrLogin(poll_timeout=10)
    account = MiAccount("", "")  # Memory-only until confirmation and cancellation check.
    try:
        emit("status", "正在申请登录二维码…")
        qr.start()
        if stop.is_set():
            return
        data = qr.fetch_qr_image()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 1_000_000:
            raise config.ConfigError("登录二维码图片格式不正确，请重试。")
        if stop.is_set():
            return
        emit("qr", data)
        emit("status", "请用米家 App 扫码，并在手机上确认")
        deadline = time.monotonic() + min(600, max(30, qr.expires_in))
        while not stop.is_set() and time.monotonic() < deadline:
            state = qr.poll()
            if stop.is_set():
                return
            if state == CONFIRMED:
                account.login_with_pass_token(SID_MINA, qr.pass_token, qr.user_id, qr.device_id)
                if stop.is_set():
                    return
                SecretStore(directory / "xiaomi.dpapi").save(account.token)
                emit("status", "登录已保存；正在获取音箱列表…")
                devices = MiNA(account).device_list()
                if not stop.is_set():
                    emit("devices", devices)
                    emit("status", "登录成功，请选择音箱并保存设置")
                return
            if state in (EXPIRED, FAILED):
                raise config.ConfigError("二维码已失效，请重新点击扫码登录。")
            if state == SCANNED:
                emit("status", "已扫描，请在手机上确认")
            stop.wait(1)
        if not stop.is_set():
            raise config.ConfigError("扫码等待超时，请重新点击扫码登录。")
    finally:
        qr._session.close()
        account._session.close()
        account.token.clear()
        emit("qr", None)


def devices(directory, stop, emit):
    account = SecureAccount(SecretStore(directory / "xiaomi.dpapi"))
    try:
        require_login(account)
        result = MiNA(account).device_list()
        if not stop.is_set():
            emit("devices", result)
            emit("status", "设备列表已刷新，请选择音箱并保存")
    finally:
        account.close()


def listen(directory, data, stop, emit):
    if not data["xiaomi"]["device_id"]:
        raise config.ConfigError("请先登录、选择音箱并保存设置。")
    account = SecureAccount(SecretStore(directory / "xiaomi.dpapi"))
    try:
        require_login(account)
        speaker = XiaomiSpeaker(account, data["xiaomi"]["device_id"])
        bridge = Bridge(speaker, CommandRouter(data), data, stop=stop,
                        on_state=lambda state: emit("bridge_state", state))
        bridge.run()
    finally:
        account.close()


def probe(directory, data, stop, emit):
    if not data["xiaomi"]["device_id"]:
        raise config.ConfigError("请先选择音箱并保存设置。")
    account = SecureAccount(SecretStore(directory / "xiaomi.dpapi"))
    try:
        require_login(account)
        records = XiaomiSpeaker(account, data["xiaomi"]["device_id"]).latest()
        if not stop.is_set():
            emit("status", f"对话接口可访问，返回 {len(records)} 条记录；没有执行历史命令")
    finally:
        account.close()
