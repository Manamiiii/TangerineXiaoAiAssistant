"""Small boundary around the reviewed VoxNode protocol implementation."""
from __future__ import annotations

from .secure import SecretStore
from .vendor.voxnode.account import MiAccount, SID_MINA, XiaomiAuthError
from .vendor.voxnode.mina import MiNA, MiNAProtocolError


class SecureAccount(MiAccount):
    def __init__(self, store: SecretStore, username: str = "", password: str = "", otp_callback=None,
                 *, load_existing: bool = True):
        self.store = store
        self.load_existing = load_existing
        super().__init__(username, password, otp_callback=otp_callback)

    def _load_token(self) -> None:
        self.token = self.store.load() if self.load_existing else {}

    def _save_token(self, token=None) -> None:
        if token:
            self.store.save(token)

    def close(self) -> None:
        self.password = ""
        self._session.close()


class XiaomiSpeaker:
    def __init__(self, account: SecureAccount, device_id: str):
        self.account = account
        self.device_id = device_id
        self.mina = MiNA(account)
        self._validated = False

    def validate_device(self) -> None:
        if not self._validated:
            devices = self.mina.device_list()
            if not any(str(d.get("deviceID", "")) == self.device_id for d in devices):
                raise MiNAProtocolError("所选音箱不在当前账号中，请运行 devices --select。")
            self._validated = True

    def latest(self) -> list[dict]:
        # This check runs inside Bridge's retry loop, including offline startup.
        self.validate_device()
        return self.mina.latest_asks(self.device_id)

    def say(self, text: str) -> bool:
        self.validate_device()
        return self.mina.tts(self.device_id, text)


def require_login(account: SecureAccount) -> None:
    if not account.is_logged_in(SID_MINA) and not account.token.get("passToken"):
        raise XiaomiAuthError("尚未登录小米账号，请先运行 login。")
